
from cod3s.utils.security import verify_password, create_access_token, hash_password
# Test de hachage et vérification du mot de passe
test_password = "nachthyamaforever"
hashed_password = hash_password(test_password)
print("Hashed Password:", hashed_password)

# Vérification du mot de passe
is_valid = verify_password("nachthyamaforever", hashed_password)
print("Password is valid:", is_valid)

is_valid_wrong = verify_password("wrongpassword", hashed_password)
print("Wrong password is valid:", is_valid_wrong)
