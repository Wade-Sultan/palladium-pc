import os

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Initialize Firebase Admin once at module load.
# On Cloud Run, Application Default Credentials work automatically via the
# attached service account. Locally, set FIREBASE_PROJECT_ID in your .env
# (and optionally GOOGLE_APPLICATION_CREDENTIALS for a service account key).
if not firebase_admin._apps:
    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    print("Firebase initial test")
    firebase_admin.initialize_app(options={"projectId": project_id} if project_id else None)

bearer_scheme = HTTPBearer(auto_error=True)


async def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Verifies the Firebase ID token from the Authorization header.
    Returns the decoded token claims (uid, email, etc.) on success.
    Raises 401 on any failure.
    """
    token = credentials.credentials
    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token expired",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )