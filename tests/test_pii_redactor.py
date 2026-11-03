from agentkit.pii.redactor import Redactor, restore_any

def r() -> Redactor:
    return Redactor(enabled=True)

def test_email_masked_and_deterministic():
    a = r().redact('mail jane.doe@acme.com now')
    b = r().redact('again jane.doe@acme.com')
    assert '[EMAIL_' in a.text and 'jane.doe@acme.com' not in a.text
    assert a.spans[0].placeholder == b.spans[0].placeholder

def test_phone_masked_but_dates_survive():
    res = r().redact('call +9999999999 before 2026-10-27')
    assert '[PHONE_' in res.text and '+9999999999' not in res.text
    assert '2026-10-27' in res.text

def test_credit_card_luhn_gate():
    good = r().redact('card 4111 1111 1111 1111')
    bad = r().redact('card 4111 1111 1111 1112')
    assert '[CREDIT_CARD_' in good.text
    assert '[CREDIT_CARD_' not in bad.text

def test_iban_mod97_gate():
    assert '[IBAN_' in r().redact('pay GB82WEST12345698765432').text
    assert '[IBAN_' not in r().redact('pay GB82WEST12345698765433').text

def test_api_keys_jwt_and_private_key():
    res = r().redact(
        'groq gsk_abcdef1234567890abcdef and openai sk-abcdef1234567890abcdef '
        'github ghp_' + 'A' * 36 + ' aws AKIAIOSFODNN7EXAMPLE jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc12345defg '
        '-----BEGIN RSA PRIVATE KEY-----\nsecret\n-----END RSA PRIVATE KEY-----'
    )
    kinds = {s.kind for s in res.spans}
    assert {'API_KEY', 'JWT', 'PRIVATE_KEY'} <= kinds

def test_national_id_gate():
    assert '[NATIONAL_ID_' in r().redact('ssn 123-45-6789').text
    assert '[NATIONAL_ID_' not in r().redact('ssn 123-00-6789').text

def test_restore_roundtrip():
    original = 'jane@acme.com / +9999999999'
    res = r().redact(original)
    assert res.restore() == original

def test_restore_any_nested_arguments():
    res = r().redact('reporter jane@acme.com')
    args = {'summary': 'crash', 'description': res.text, 'tags': [res.text]}
    restored = restore_any(args, res.mapping)
    assert restored['description'] == 'reporter jane@acme.com'
    assert restored['tags'][0] == 'reporter jane@acme.com'

def test_benign_text_untouched():
    text = 'Deploy v1.2.3 on 2026-10-27, see ENG-12, page 42, order 100000123'
    assert r().redact(text).text == text