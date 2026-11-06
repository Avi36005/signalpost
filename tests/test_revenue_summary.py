import pytest

from aviscope.extract import revenue_comparison, summarize
from aviscope.models import Profile, add_claim

ORG = '945811714'
SNAP = {'id': 'sn-test', 'final_url': 'https://data.brreg.no/regnskapsregisteret/regnskap/' + ORG, 'source_class': 'official_registry',
        'retrieved_at': '2026-11-06T00:00:00Z', 'content_sha256': '0' * 64}


def period(year, start_month=1):
    return {'fraDato': f'{year}-{start_month:02d}-01', 'tilDato': f'{year}-12-31'}


def profile(rows, scope='legal_entity'):
    p = Profile(organisation_number=ORG, name='AMBITA AS').model_dump(mode='json')
    for i, row in enumerate(rows):
        year, value = row[0], row[1]
        currency = row[2] if len(row) > 2 else 'NOK'
        months_start = row[3] if len(row) > 3 else 1
        add_claim(p, 'financials', 'revenue', value, SNAP, f'/{i}/rev', period=period(year, months_start), currency=currency,
                  unit='currency units (API numeric value)', scope=row[4] if len(row) > 4 else scope)
    summarize(p)
    return p


def sentence(p):
    return next(x for x in p['summary']['narrative'] if x['text'].startswith('Revenue was'))


def test_positive_change_cites_both_claims():
    p = profile([(2025, 12_000_000), (2024, 10_000_000), (2023, 9_000_000)])
    s = sentence(p)
    assert s['text'] == 'Revenue was NOK 12.0 million in 2025, up from NOK 10.0 million in 2024, an increase of NOK 2.0 million (20.0%).'
    ids = {c['period']['tilDato'][:4]: c['id'] for c in p['claims']}
    assert s['claim_ids'] == [ids['2025'], ids['2024']]
    fact = next(f for f in p['summary']['facts'] if f['field'] == 'revenue_change')
    assert fact['derived_from'] == [ids['2025'], ids['2024']] and fact['value']['percent_change'] == 20.0


def test_decrease_and_unchanged():
    assert 'down from NOK 10.0 million in 2024, a decrease of NOK 2.5 million (25.0%)' in sentence(profile([(2025, 7_500_000), (2024, 10_000_000)]))['text']
    assert sentence(profile([(2025, 500_000), (2024, 500_000)]))['text'] == 'Revenue was NOK 500,000 in 2025, unchanged from 2024.'


@pytest.mark.parametrize('previous,phrase', [(0, 'preceding revenue was zero'), (-1000, 'preceding revenue was negative')])
def test_zero_or_negative_prior_has_absolute_change_only(previous, phrase):
    p = profile([(2025, 100_000), (2024, previous)])
    text = sentence(p)['text']
    assert 'increase of NOK' in text and phrase in text and '%' not in text
    assert p['summary']['revenue_comparison']['percent_change'] is None


def test_nonconsecutive_years_are_not_called_year_on_year():
    text = sentence(profile([(2025, 12_000_000), (2023, 10_000_000)]))['text']
    assert 'compared with NOK 10.0 million in the available 2023 record' in text and 'up from' not in text


def test_short_latest_period_is_not_compared_or_annualised():
    p = profile([(2025, 6_000_000, 'NOK', 7), (2024, 10_000_000)])
    assert p['summary']['revenue_comparison']['status'] == 'latest_period_short'
    assert 'not compared' in sentence(p)['text'] and len(sentence(p)['claim_ids']) == 1


def test_currency_mismatch_and_group_scope_are_not_compared():
    assert revenue_comparison(profile([(2025, 1_000_000, 'EUR'), (2024, 900_000, 'NOK')])['claims'])['status'] == 'not_comparable'
    # A group-scope record is never used as either side of a legal-entity comparison.
    p = profile([(2025, 1_000_000), (2024, 900_000, 'NOK', 1, 'group')])
    assert p['summary']['revenue_comparison']['status'] == 'no_prior_record'


def test_missing_revenue_never_becomes_zero():
    p = profile([])
    assert p['summary']['revenue_comparison'] is None
    assert not any('Revenue' in x['text'] for x in p['summary']['narrative'])


def test_single_year_explains_absence_of_comparison():
    text = sentence(profile([(2025, 1_000_000)]))['text']
    assert text.startswith('Revenue was NOK 1.0 million in 2025. No prior-year comparison is shown')
