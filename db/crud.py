from models.user import UserInDB, Role, PyObjectId

from .database import get_database
from typing import List

# Fonction pour créer un nouvel utilisateur avec des rôles
async def create_user(user_data: UserInDB, roles: List[Role] = [Role.user]) -> UserInDB:
    db = get_database()
    collection = db["users"]
    from cod3s.utils.security import hash_password
    
    # Hacher le mot de passe ici
    user_data.password = hash_password(user_data.password)
    
    # Si des rôles sont fournis, utilisez-les, sinon attribuez le rôle utilisateur par défaut
    user_data.roles = roles
    
    # Préparation des données pour l'insertion en excluant 'id' et en utilisant 'by_alias'
    user_dict = user_data.dict(by_alias=True, exclude={"id"})
    
    # Insertion dans la base de données
    row = await collection.insert_one(user_dict)
    
    # Mise à jour de l'id de l'utilisateur avec celui attribué par MongoDB
    user_data.id = row.inserted_id
    
    return user_data


async def get_user_by_email(email: str) -> UserInDB:
    db = get_database()
    collection = db["users"]
    user_data = await collection.find_one({"email": email})
    #print("User Data:", user_data)  # Ajoutez ce log pour voir ce qui est récupéré
    if user_data:
        return UserInDB(**user_data)
    else:
        return None

    
async def get_user_roles(user_id: PyObjectId) -> List[Role]:
    db = get_database()
    collection = db["users"]
    user = await collection.find_one({"_id": user_id})
    if user and "roles" in user:
        # Convertit les rôles en une liste de `Role` s'ils ne sont pas déjà convertis
        return [Role(role) for role in user["roles"]]
    else:
        # Si l'utilisateur n'a pas de rôles définis, retourne une liste avec le rôle par défaut 'user'
        return [Role.user]
