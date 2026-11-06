import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('package_submission', Path(__file__).resolve().parents[1] / 'scripts' / 'package_submission.py')
package_submission = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package_submission)
SECRET = package_submission.SECRET


def test_secret_scan_flags_real_token_shapes():
    for sample in (b'key=sk-' + b'A' * 40, b'"sk-proj-' + b'x' * 40 + b'"', b' ghp_' + b'a' * 36,
                   b'github_pat_' + b'b' * 45, b'-----BEGIN ' + b'PRIVATE KEY-----'):
        assert SECRET.search(sample), sample


def test_secret_scan_ignores_words_ending_in_sk_or_gh():
    for sample in (b'/uploads/Rival-Country-02.nordisk-eik-' + b'l' * 40 + b'.png',
                   b'risk-assessment-' + b'z' * 40, b'high_' + b'q' * 36):
        assert not SECRET.search(sample), sample
