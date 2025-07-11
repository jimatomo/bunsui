"""
Authentication middleware for Bunsui.
"""

import functools
from typing import Optional, Callable
from .authenticator import Authenticator, Credentials
from .rbac import RBACManager
from .token_manager import TokenManager


class AuthMiddleware:
    """認証・認可ミドルウェア"""
    
    def __init__(self, authenticator: Authenticator, rbac_manager: RBACManager, token_manager: TokenManager):
        self.authenticator = authenticator
        self.rbac_manager = rbac_manager
        self.token_manager = token_manager
    
    def require_auth(self, resource: str, action: str):
        """認証・認可を要求するデコレータ"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # コンテキストからトークンを取得
                token = self._extract_token_from_context(args, kwargs)
                
                if not token:
                    raise AuthError("Authentication token required")
                
                # トークンを検証
                auth_token = self.authenticator.verify_token(token)
                if auth_token.status != auth_token.status.SUCCESS:
                    raise AuthError("Invalid or expired token")
                
                # 権限をチェック
                if not self.authenticator.authorize(auth_token, resource, action):
                    raise AuthError(f"Insufficient permissions for {resource}:{action}")
                
                # ユーザーIDをコンテキストに追加
                self._add_user_to_context(args, kwargs, auth_token.user_id)
                
                return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def require_role(self, role_name: str):
        """特定のロールを要求するデコレータ"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # コンテキストからユーザーIDを取得
                user_id = self._extract_user_from_context(args, kwargs)
                
                if not user_id:
                    raise AuthError("User ID required")
                
                # ロールをチェック
                user_roles = self.rbac_manager.get_user_roles(user_id)
                if role_name not in user_roles:
                    raise AuthError(f"Role '{role_name}' required")
                
                return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def require_permission(self, resource: str, action: str):
        """特定の権限を要求するデコレータ"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # コンテキストからユーザーIDを取得
                user_id = self._extract_user_from_context(args, kwargs)
                
                if not user_id:
                    raise AuthError("User ID required")
                
                # 権限をチェック
                if not self.rbac_manager.has_permission(user_id, resource, action):
                    raise AuthError(f"Permission '{resource}:{action}' required")
                
                return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def _extract_token_from_context(self, args: tuple, kwargs: dict) -> Optional[str]:
        """コンテキストからトークンを抽出"""
        # Clickコンテキストから取得を試行
        if args and hasattr(args[0], 'obj') and isinstance(args[0].obj, dict):
            return args[0].obj.get('auth_token')
        
        # キーワード引数から取得を試行
        return kwargs.get('auth_token')
    
    def _extract_user_from_context(self, args: tuple, kwargs: dict) -> Optional[str]:
        """コンテキストからユーザーIDを抽出"""
        # Clickコンテキストから取得を試行
        if args and hasattr(args[0], 'obj') and isinstance(args[0].obj, dict):
            return args[0].obj.get('user_id')
        
        # キーワード引数から取得を試行
        return kwargs.get('user_id')
    
    def _add_user_to_context(self, args: tuple, kwargs: dict, user_id: str):
        """コンテキストにユーザーIDを追加"""
        # Clickコンテキストに追加
        if args and hasattr(args[0], 'obj') and isinstance(args[0].obj, dict):
            args[0].obj['user_id'] = user_id
        
        # キーワード引数に追加
        kwargs['user_id'] = user_id


class AuthError(Exception):
    """認証エラー"""
    pass


class AuthContext:
    """認証コンテキスト"""
    
    def __init__(self, user_id: str, permissions: list[str], token: Optional[str] = None):
        self.user_id = user_id
        self.permissions = permissions
        self.token = token
        self._rbac_manager: Optional[RBACManager] = None
    
    def has_permission(self, resource: str, action: str) -> bool:
        """権限をチェック"""
        required_permission = f"{resource}:{action}"
        wildcard_permission = f"{resource}:*"
        admin_permission = "*:*"
        
        return (required_permission in self.permissions or
                wildcard_permission in self.permissions or
                admin_permission in self.permissions)
    
    def has_role(self, role_name: str) -> bool:
        """ロールをチェック"""
        if not self._rbac_manager:
            return False
        
        user_roles = self._rbac_manager.get_user_roles(self.user_id)
        return role_name in user_roles
    
    def set_rbac_manager(self, rbac_manager: RBACManager):
        """RBACマネージャーを設定"""
        self._rbac_manager = rbac_manager


class AuthManager:
    """認証マネージャー"""
    
    def __init__(self, region: str = "us-east-1"):
        self.authenticator = Authenticator(region)
        self.rbac_manager = RBACManager()
        self.token_manager = TokenManager()
        self.middleware = AuthMiddleware(self.authenticator, self.rbac_manager, self.token_manager)
    
    def authenticate_user(self, credentials: Credentials) -> AuthContext:
        """ユーザーを認証"""
        auth_token = self.authenticator.authenticate(credentials)
        
        if auth_token.status != auth_token.status.SUCCESS:
            raise AuthError("Authentication failed")
        
        # セッショントークンを作成
        session_token = self.token_manager.create_token(
            user_id=auth_token.user_id,
            permissions=auth_token.permissions
        )
        
        # 認証コンテキストを作成
        context = AuthContext(
            user_id=auth_token.user_id,
            permissions=auth_token.permissions,
            token=session_token
        )
        context.set_rbac_manager(self.rbac_manager)
        
        return context
    
    def validate_session(self, session_token: str) -> AuthContext:
        """セッションを検証"""
        token_info = self.token_manager.validate_token(session_token)
        
        if not token_info:
            raise AuthError("Invalid or expired session token")
        
        # 認証コンテキストを作成
        context = AuthContext(
            user_id=token_info.user_id,
            permissions=token_info.permissions,
            token=session_token
        )
        context.set_rbac_manager(self.rbac_manager)
        
        return context
    
    def create_api_key(self, user_id: str, permissions: list[str], 
                      expires_in_hours: int = 8760) -> str:  # 1年
        """APIキーを作成"""
        return self.token_manager.create_token(
            user_id=user_id,
            permissions=permissions,
            expires_in_hours=expires_in_hours
        )
    
    def validate_api_key(self, api_key: str) -> AuthContext:
        """APIキーを検証"""
        token_info = self.token_manager.validate_token(api_key)
        
        if not token_info:
            raise AuthError("Invalid or expired API key")
        
        # 認証コンテキストを作成
        context = AuthContext(
            user_id=token_info.user_id,
            permissions=token_info.permissions,
            token=api_key
        )
        context.set_rbac_manager(self.rbac_manager)
        
        return context
    
    def revoke_token(self, token: str) -> bool:
        """トークンを無効化"""
        return self.token_manager.revoke_token(token)
    
    def assign_role(self, user_id: str, role_name: str) -> bool:
        """ユーザーにロールを割り当て"""
        return self.rbac_manager.assign_role(user_id, role_name)
    
    def revoke_role(self, user_id: str, role_name: str) -> bool:
        """ユーザーからロールを削除"""
        return self.rbac_manager.revoke_role(user_id, role_name)
    
    def get_user_permissions(self, user_id: str) -> list[str]:
        """ユーザーの権限を取得"""
        permissions = set()
        
        # ロールベースの権限
        user_roles = self.rbac_manager.get_user_roles(user_id)
        for role_name in user_roles:
            role_permissions = self.rbac_manager.get_role_permissions(role_name)
            permissions.update(role_permissions)
        
        return list(permissions)
    
    def cleanup_expired_tokens(self) -> int:
        """期限切れトークンを削除"""
        return self.token_manager.cleanup_expired_tokens()
    
    def get_auth_stats(self) -> dict:
        """認証統計を取得"""
        token_stats = self.token_manager.get_token_stats()
        role_stats = {
            "total_roles": len(self.rbac_manager.list_roles()),
            "total_users": len(set(
                user_id for user_id, roles in self.rbac_manager._user_roles.items()
            ))
        }
        
        return {
            "tokens": token_stats,
            "roles": role_stats
        } 