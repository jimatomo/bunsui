"""
Authentication management for Bunsui.
"""

import boto3
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
import jwt
import secrets
from enum import Enum


class AuthStatus(Enum):
    """Authentication status enumeration."""
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    INVALID = "invalid"


@dataclass
class Credentials:
    """Credentials for authentication."""
    access_key_id: str
    secret_access_key: str
    session_token: Optional[str] = None
    profile: Optional[str] = None


@dataclass
class AuthToken:
    """Authentication token."""
    token: str
    expires_at: datetime
    user_id: str
    permissions: list[str]
    status: AuthStatus = AuthStatus.SUCCESS


class Authenticator:
    """認証を管理するクラス"""
    
    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self._tokens: Dict[str, AuthToken] = {}
        self._secret_key = secrets.token_hex(32)
    
    def authenticate(self, credentials: Credentials) -> AuthToken:
        """認証を実行"""
        try:
            # AWS認証情報を検証
            session = boto3.Session(
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key,
                aws_session_token=credentials.session_token,
                region_name=self.region
            )
            
            # STSを使用して認証情報を検証
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            
            # ユーザーIDを取得
            user_id = identity.get('UserId', 'unknown')
            account_id = identity.get('Account', 'unknown')
            arn = identity.get('Arn', 'unknown')
            
            # 権限を取得
            permissions = self._get_permissions(session, arn)
            
            # トークンを生成
            token_data = {
                'user_id': user_id,
                'account_id': account_id,
                'arn': arn,
                'permissions': permissions,
                'exp': datetime.utcnow() + timedelta(hours=24)
            }
            
            token = jwt.encode(token_data, self._secret_key, algorithm='HS256')
            
            auth_token = AuthToken(
                token=token,
                expires_at=token_data['exp'],
                user_id=user_id,
                permissions=permissions
            )
            
            # トークンを保存
            self._tokens[token] = auth_token
            
            return auth_token
            
        except Exception as e:
            return AuthToken(
                token="",
                expires_at=datetime.utcnow(),
                user_id="",
                permissions=[],
                status=AuthStatus.FAILED
            )
    
    def verify_token(self, token: str) -> AuthToken:
        """トークンを検証"""
        try:
            # トークンをデコード
            payload = jwt.decode(token, self._secret_key, algorithms=['HS256'])
            
            # 有効期限をチェック
            exp_timestamp = payload.get('exp')
            if exp_timestamp:
                exp_datetime = datetime.fromtimestamp(exp_timestamp)
                if datetime.utcnow() > exp_datetime:
                    return AuthToken(
                        token=token,
                        expires_at=exp_datetime,
                        user_id=payload.get('user_id', ''),
                        permissions=payload.get('permissions', []),
                        status=AuthStatus.EXPIRED
                    )
            
            # 保存されたトークンと比較
            if token in self._tokens:
                return self._tokens[token]
            
            # 新しいトークンとして保存
            auth_token = AuthToken(
                token=token,
                expires_at=datetime.fromtimestamp(exp_timestamp) if exp_timestamp else datetime.utcnow(),
                user_id=payload.get('user_id', ''),
                permissions=payload.get('permissions', [])
            )
            
            self._tokens[token] = auth_token
            return auth_token
            
        except jwt.InvalidTokenError:
            return AuthToken(
                token=token,
                expires_at=datetime.utcnow(),
                user_id="",
                permissions=[],
                status=AuthStatus.INVALID
            )
    
    def authorize(self, token: AuthToken, resource: str, action: str) -> bool:
        """権限をチェック"""
        if token.status != AuthStatus.SUCCESS:
            return False
        
        # 権限パターンをチェック
        required_permission = f"{resource}:{action}"
        
        # ワイルドカード権限をチェック
        wildcard_permission = f"{resource}:*"
        admin_permission = "*:*"
        
        return (required_permission in token.permissions or
                wildcard_permission in token.permissions or
                admin_permission in token.permissions)
    
    def _get_permissions(self, session: boto3.Session, arn: str) -> list[str]:
        """AWS IAMから権限を取得"""
        try:
            iam = session.client('iam')
            
            # ユーザーのポリシーを取得
            policies = []
            
            # インラインポリシー
            try:
                inline_policies = iam.list_user_policies(UserName=arn.split('/')[-1])
                for policy_name in inline_policies.get('PolicyNames', []):
                    policy = iam.get_user_policy(UserName=arn.split('/')[-1], PolicyName=policy_name)
                    policies.append(policy['PolicyDocument'])
            except:
                pass
            
            # アタッチされたポリシー
            try:
                attached_policies = iam.list_attached_user_policies(UserName=arn.split('/')[-1])
                for policy in attached_policies.get('AttachedPolicies', []):
                    policy_arn = policy['PolicyArn']
                    policy_version = iam.get_policy_default_version(PolicyArn=policy_arn)
                    policy_doc = iam.get_policy_version(
                        PolicyArn=policy_arn,
                        VersionId=policy_version['DefaultVersionId']
                    )
                    policies.append(policy_doc['PolicyVersion']['Document'])
            except:
                pass
            
            # 権限を抽出
            permissions = []
            for policy in policies:
                if 'Statement' in policy:
                    for statement in policy['Statement']:
                        if statement.get('Effect') == 'Allow':
                            action = statement.get('Action', [])
                            if isinstance(action, str):
                                permissions.append(action)
                            elif isinstance(action, list):
                                permissions.extend(action)
            
            return list(set(permissions))
            
        except Exception:
            # デフォルト権限
            return ["bunsui:*"]
    
    def revoke_token(self, token: str) -> bool:
        """トークンを無効化"""
        if token in self._tokens:
            del self._tokens[token]
            return True
        return False
    
    def cleanup_expired_tokens(self) -> int:
        """期限切れトークンを削除"""
        now = datetime.utcnow()
        expired_tokens = [
            token for token, auth_token in self._tokens.items()
            if auth_token.expires_at < now
        ]
        
        for token in expired_tokens:
            del self._tokens[token]
        
        return len(expired_tokens) 