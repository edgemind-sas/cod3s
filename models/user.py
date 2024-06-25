from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from bson import ObjectId
from pydantic.networks import EmailStr
from enum import Enum
from typing import Optional, List

# Custom type pour ObjectId afin qu'il soit correctement converti en string
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")
    
class Role(str, Enum):
    user = "user"
    admin = "admin"

# Modèle de base pour un utilisateur incluant le mot de passe
class UserInDB(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias='_id')
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    roles: List[Role] = []

    class Config:
        json_encoders = {
            ObjectId: str
        }
        allow_population_by_field_name = True
        arbitrary_types_allowed = True

# Modèle de réponse qui sera utilisé pour renvoyer les données utilisateur,
# excluant le mot de passe
class UserPublic(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias='_id')
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[EmailStr]

    class Config:
        json_encoders = {
            ObjectId: str
        }
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        schema_extra = {
            "example": {
                "first_name": "Abderrahim",
                "last_name": "IZMAR",
                "email": "a.izmar@example.com",
            }
        }

class TokenData(BaseModel):
    access_token: str
    token_type: str

class UserPublicWithToken(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[EmailStr]
    access_token: str
    token_type: str

    class Config:
        json_encoders = {
            ObjectId: str
        }
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        schema_extra = {
            "example": {
                "first_name": "Abderrahim",
                "last_name": "IZMAR",
                "email": "a.izmar@example.com",
                "access_token": "example_access_token",
                "token_type": "bearer"
            }
        }
