"""
Role-based access control (RBAC) for Bunsui.
"""

from enum import Enum
from typing import List, Dict, Set, Optional
from dataclasses import dataclass


class Role(Enum):
    """Role enumeration."""
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    OPERATOR = "operator"


@dataclass
class Permission:
    """Permission definition."""
    resource: str
    actions: List[str]
    conditions: Optional[Dict] = None


@dataclass
class RoleDefinition:
    """Role definition with permissions."""
    name: str
    description: str
    permissions: List[Permission]
    inherits: Optional[List[str]] = None


class RBACManager:
    """ロールベースアクセス制御を管理するクラス"""
    
    def __init__(self):
        self._roles: Dict[str, RoleDefinition] = {}
        self._user_roles: Dict[str, Set[str]] = {}
        self._role_permissions: Dict[str, Set[str]] = {}
        
        # デフォルトロールを初期化
        self._initialize_default_roles()
    
    def _initialize_default_roles(self):
        """デフォルトロールを初期化"""
        # Admin role
        admin_permissions = [
            Permission("pipeline", ["create", "read", "update", "delete", "execute"]),
            Permission("session", ["create", "read", "update", "delete", "control"]),
            Permission("logs", ["read", "download", "filter"]),
            Permission("config", ["read", "write", "delete"]),
            Permission("user", ["create", "read", "update", "delete"]),
            Permission("role", ["create", "read", "update", "delete"]),
            Permission("*", ["*"])
        ]
        
        self.add_role("admin", "Administrator with full access", admin_permissions)
        
        # Developer role
        developer_permissions = [
            Permission("pipeline", ["create", "read", "update", "execute"]),
            Permission("session", ["create", "read", "control"]),
            Permission("logs", ["read", "download", "filter"]),
            Permission("config", ["read", "write"])
        ]
        
        self.add_role("developer", "Developer with pipeline management access", developer_permissions)
        
        # Viewer role
        viewer_permissions = [
            Permission("pipeline", ["read"]),
            Permission("session", ["read"]),
            Permission("logs", ["read"])
        ]
        
        self.add_role("viewer", "Viewer with read-only access", viewer_permissions)
        
        # Operator role
        operator_permissions = [
            Permission("pipeline", ["read", "execute"]),
            Permission("session", ["create", "read", "control"]),
            Permission("logs", ["read", "download"]),
            Permission("config", ["read"])
        ]
        
        self.add_role("operator", "Operator with execution access", operator_permissions)
    
    def add_role(self, name: str, description: str, permissions: List[Permission], inherits: Optional[List[str]] = None):
        """ロールを追加"""
        role = RoleDefinition(
            name=name,
            description=description,
            permissions=permissions,
            inherits=inherits or []
        )
        
        self._roles[name] = role
        self._build_permission_cache(name)
    
    def remove_role(self, name: str) -> bool:
        """ロールを削除"""
        if name in self._roles:
            del self._roles[name]
            if name in self._role_permissions:
                del self._role_permissions[name]
            return True
        return False
    
    def assign_role(self, user_id: str, role_name: str) -> bool:
        """ユーザーにロールを割り当て"""
        if role_name not in self._roles:
            return False
        
        if user_id not in self._user_roles:
            self._user_roles[user_id] = set()
        
        self._user_roles[user_id].add(role_name)
        return True
    
    def revoke_role(self, user_id: str, role_name: str) -> bool:
        """ユーザーからロールを削除"""
        if user_id in self._user_roles and role_name in self._user_roles[user_id]:
            self._user_roles[user_id].remove(role_name)
            return True
        return False
    
    def get_user_roles(self, user_id: str) -> List[str]:
        """ユーザーのロールを取得"""
        return list(self._user_roles.get(user_id, set()))
    
    def has_permission(self, user_id: str, resource: str, action: str) -> bool:
        """ユーザーが権限を持っているかチェック"""
        user_roles = self.get_user_roles(user_id)
        
        for role_name in user_roles:
            if self._check_role_permission(role_name, resource, action):
                return True
        
        return False
    
    def _check_role_permission(self, role_name: str, resource: str, action: str) -> bool:
        """ロールの権限をチェック"""
        if role_name not in self._role_permissions:
            return False
        
        permissions = self._role_permissions[role_name]
        
        # 具体的な権限をチェック
        specific_permission = f"{resource}:{action}"
        if specific_permission in permissions:
            return True
        
        # ワイルドカード権限をチェック
        resource_wildcard = f"{resource}:*"
        if resource_wildcard in permissions:
            return True
        
        # 全体のワイルドカードをチェック
        if "*:*" in permissions:
            return True
        
        return False
    
    def _build_permission_cache(self, role_name: str):
        """ロールの権限キャッシュを構築"""
        if role_name not in self._roles:
            return
        
        role = self._roles[role_name]
        permissions = set()
        
        # 継承されたロールの権限を追加
        if role.inherits:
            for inherited_role in role.inherits:
                if inherited_role in self._role_permissions:
                    permissions.update(self._role_permissions[inherited_role])
        
        # 現在のロールの権限を追加
        for permission in role.permissions:
            for action in permission.actions:
                if action == "*":
                    # ワイルドカードアクション
                    if permission.resource == "*":
                        permissions.add("*:*")
                    else:
                        permissions.add(f"{permission.resource}:*")
                else:
                    permissions.add(f"{permission.resource}:{action}")
        
        self._role_permissions[role_name] = permissions
    
    def get_role_permissions(self, role_name: str) -> List[str]:
        """ロールの権限を取得"""
        return list(self._role_permissions.get(role_name, set()))
    
    def list_roles(self) -> List[Dict]:
        """ロール一覧を取得"""
        roles = []
        for name, role in self._roles.items():
            roles.append({
                "name": name,
                "description": role.description,
                "permissions": self.get_role_permissions(name),
                "inherits": role.inherits
            })
        return roles
    
    def get_role_users(self, role_name: str) -> List[str]:
        """ロールを持つユーザー一覧を取得"""
        users = []
        for user_id, roles in self._user_roles.items():
            if role_name in roles:
                users.append(user_id)
        return users
    
    def validate_permission(self, resource: str, action: str) -> bool:
        """権限の形式を検証"""
        # 基本的な形式チェック
        if not resource or not action:
            return False
        
        # リソース名の形式チェック
        if not resource.replace(".", "").replace("-", "").replace("_", "").isalnum():
            return False
        
        # アクション名の形式チェック
        if not action.replace("-", "").replace("_", "").isalnum():
            return False
        
        return True
    
    def create_custom_role(self, name: str, description: str, permissions: List[Dict], inherits: Optional[List[str]] = None) -> bool:
        """カスタムロールを作成"""
        try:
            # 権限を検証
            permission_objects = []
            for perm_dict in permissions:
                if "resource" not in perm_dict or "actions" not in perm_dict:
                    return False
                
                # 権限の形式を検証
                if not self.validate_permission(perm_dict["resource"], perm_dict["actions"][0]):
                    return False
                
                permission_objects.append(Permission(
                    resource=perm_dict["resource"],
                    actions=perm_dict["actions"],
                    conditions=perm_dict.get("conditions")
                ))
            
            # 継承ロールを検証
            if inherits:
                for inherited_role in inherits:
                    if inherited_role not in self._roles:
                        return False
            
            self.add_role(name, description, permission_objects, inherits)
            return True
            
        except Exception:
            return False
    
    def export_role_definition(self, role_name: str) -> Optional[Dict]:
        """ロール定義をエクスポート"""
        if role_name not in self._roles:
            return None
        
        role = self._roles[role_name]
        return {
            "name": role.name,
            "description": role.description,
            "permissions": [
                {
                    "resource": perm.resource,
                    "actions": perm.actions,
                    "conditions": perm.conditions
                }
                for perm in role.permissions
            ],
            "inherits": role.inherits
        }
    
    def import_role_definition(self, role_def: Dict) -> bool:
        """ロール定義をインポート"""
        try:
            name = role_def.get("name")
            description = role_def.get("description", "")
            permissions_data = role_def.get("permissions", [])
            inherits = role_def.get("inherits", [])
            
            if not name:
                return False
            
            # 権限オブジェクトを作成
            permissions = []
            for perm_data in permissions_data:
                permissions.append(Permission(
                    resource=perm_data["resource"],
                    actions=perm_data["actions"],
                    conditions=perm_data.get("conditions")
                ))
            
            self.add_role(name, description, permissions, inherits)
            return True
            
        except Exception:
            return False 