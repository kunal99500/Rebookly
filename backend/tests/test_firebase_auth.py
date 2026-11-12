import time

import jwt, pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from app.auth.firebase_auth import AuthVerifier, FirebaseTokenVerifier, firebase_user_uuid
from app.auth.supabase_auth import AuthError

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PROJECT = "rebookly-dev"

class FakeKeys:
    def get_signing_key_from_jwt(self, token):
        class K: key = KEY.public_key()
        return K()

def token(key=KEY, **changes):
    now = int(time.time())
    claims = {"iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT, "sub": "firebase-uid-123",
              "iat": now, "exp": now + 3600, "phone_number": "+919720072866"}
    claims.update(changes)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "k1"})

verifier = FirebaseTokenVerifier(PROJECT, keys=FakeKeys())

def test_valid_firebase_token():
    user = verifier.verify(token())
    assert user.phone == "+919720072866" and user.id == firebase_user_uuid("firebase-uid-123")
    assert user.id == firebase_user_uuid("firebase-uid-123")       # stable for the same person

@pytest.mark.parametrize("changes", [{"aud": "someone-else"}, {"iss": "https://securetoken.google.com/other"},
                                     {"exp": int(time.time()) - 600}])
def test_wrong_project_or_expired_is_refused(changes):
    with pytest.raises(AuthError):
        verifier.verify(token(**changes))

def test_wrong_signature_is_refused():
    with pytest.raises(AuthError):
        verifier.verify(token(key=OTHER))

def test_the_right_verifier_is_chosen():
    class Supa:
        def verify(self, t): return "supabase"
    chooser = AuthVerifier(supabase=Supa(), firebase=verifier)
    assert chooser.verify(token()).phone == "+919720072866"
    supa_token = jwt.encode({"iss": "https://x.supabase.co/auth/v1", "sub": "u"}, "s", algorithm="HS256")
    assert chooser.verify(supa_token) == "supabase"
    with pytest.raises(AuthError):
        AuthVerifier(supabase=Supa()).verify(token())
