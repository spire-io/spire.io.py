import spire
print spire.Client('http://localhost:1337').create_account(
    'alice@example.com',
    'password',
    )
