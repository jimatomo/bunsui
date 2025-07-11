"""
Token management for Bunsui authentication.
"""

import secrets
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import os


@dataclass
class TokenInfo:
    """Token information."""
    token_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    permissions: List[str]
    is_active: bool = True
    last_used: Optional[datetime] = None


class TokenManager:
    """セッショントークンを管理するクラス"""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.path.expanduser("~/.bunsui/tokens.json")
        self._tokens: Dict[str, TokenInfo] = {}
        self._load_tokens()
    
    def create_token(self, user_id: str, permissions: List[str], 
                    expires_in_hours: int = 24) -> str:
        """新しいトークンを作成"""
        token_id = self._generate_token_id()
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=expires_in_hours)
        
        token_info = TokenInfo(
            token_id=token_id,
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
            permissions=permissions
        )
        
        self._tokens[token_id] = token_info
        self._save_tokens()
        
        return token_id
    
    def validate_token(self, token_id: str) -> Optional[TokenInfo]:
        """トークンを検証"""
        if token_id not in self._tokens:
            return None
        
        token_info = self._tokens[token_id]
        
        # 有効期限をチェック
        if datetime.utcnow() > token_info.expires_at:
            return None
        
        # アクティブかチェック
        if not token_info.is_active:
            return None
        
        # 最終使用時刻を更新
        token_info.last_used = datetime.utcnow()
        self._save_tokens()
        
        return token_info
    
    def revoke_token(self, token_id: str) -> bool:
        """トークンを無効化"""
        if token_id in self._tokens:
            self._tokens[token_id].is_active = False
            self._save_tokens()
            return True
        return False
    
    def get_user_tokens(self, user_id: str) -> List[TokenInfo]:
        """ユーザーのトークン一覧を取得"""
        return [
            token_info for token_info in self._tokens.values()
            if token_info.user_id == user_id
        ]
    
    def cleanup_expired_tokens(self) -> int:
        """期限切れトークンを削除"""
        now = datetime.utcnow()
        expired_tokens = [
            token_id for token_id, token_info in self._tokens.items()
            if token_info.expires_at < now
        ]
        
        for token_id in expired_tokens:
            del self._tokens[token_id]
        
        self._save_tokens()
        return len(expired_tokens)
    
    def get_token_stats(self) -> Dict:
        """トークン統計を取得"""
        now = datetime.utcnow()
        active_tokens = 0
        expired_tokens = 0
        total_tokens = len(self._tokens)
        
        for token_info in self._tokens.values():
            if token_info.expires_at < now:
                expired_tokens += 1
            elif token_info.is_active:
                active_tokens += 1
        
        return {
            "total_tokens": total_tokens,
            "active_tokens": active_tokens,
            "expired_tokens": expired_tokens,
            "inactive_tokens": total_tokens - active_tokens - expired_tokens
        }
    
    def _generate_token_id(self) -> str:
        """トークンIDを生成"""
        return secrets.token_urlsafe(32)
    
    def _load_tokens(self):
        """トークンをファイルから読み込み"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    
                for token_data in data.get('tokens', []):
                    token_info = TokenInfo(
                        token_id=token_data['token_id'],
                        user_id=token_data['user_id'],
                        created_at=datetime.fromisoformat(token_data['created_at']),
                        expires_at=datetime.fromisoformat(token_data['expires_at']),
                        permissions=token_data['permissions'],
                        is_active=token_data.get('is_active', True),
                        last_used=datetime.fromisoformat(token_data['last_used']) if token_data.get('last_used') else None
                    )
                    self._tokens[token_info.token_id] = token_info
        except Exception:
            # ファイルが存在しないか、読み込みエラーの場合は空の状態で開始
            pass
    
    def _save_tokens(self):
        """トークンをファイルに保存"""
        try:
            # ディレクトリを作成
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            data = {
                'tokens': []
            }
            
            for token_info in self._tokens.values():
                token_data = {
                    'token_id': token_info.token_id,
                    'user_id': token_info.user_id,
                    'created_at': token_info.created_at.isoformat(),
                    'expires_at': token_info.expires_at.isoformat(),
                    'permissions': token_info.permissions,
                    'is_active': token_info.is_active,
                    'last_used': token_info.last_used.isoformat() if token_info.last_used else None
                }
                data['tokens'].append(token_data)
            
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception:
            # 保存エラーの場合は無視
            pass
    
    def export_tokens(self, output_path: str) -> bool:
        """トークンをエクスポート"""
        try:
            data = {
                'exported_at': datetime.utcnow().isoformat(),
                'tokens': []
            }
            
            for token_info in self._tokens.values():
                token_data = {
                    'token_id': token_info.token_id,
                    'user_id': token_info.user_id,
                    'created_at': token_info.created_at.isoformat(),
                    'expires_at': token_info.expires_at.isoformat(),
                    'permissions': token_info.permissions,
                    'is_active': token_info.is_active,
                    'last_used': token_info.last_used.isoformat() if token_info.last_used else None
                }
                data['tokens'].append(token_data)
            
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception:
            return False
    
    def import_tokens(self, input_path: str) -> bool:
        """トークンをインポート"""
        try:
            with open(input_path, 'r') as f:
                data = json.load(f)
            
            imported_count = 0
            for token_data in data.get('tokens', []):
                token_info = TokenInfo(
                    token_id=token_data['token_id'],
                    user_id=token_data['user_id'],
                    created_at=datetime.fromisoformat(token_data['created_at']),
                    expires_at=datetime.fromisoformat(token_data['expires_at']),
                    permissions=token_data['permissions'],
                    is_active=token_data.get('is_active', True),
                    last_used=datetime.fromisoformat(token_data['last_used']) if token_data.get('last_used') else None
                )
                
                # 既存のトークンと重複しないようにチェック
                if token_info.token_id not in self._tokens:
                    self._tokens[token_info.token_id] = token_info
                    imported_count += 1
            
            self._save_tokens()
            return True
            
        except Exception:
            return False
    
    def rotate_tokens(self, user_id: str) -> List[str]:
        """ユーザーのトークンをローテーション"""
        user_tokens = self.get_user_tokens(user_id)
        new_tokens = []
        
        for token_info in user_tokens:
            if token_info.is_active:
                # 新しいトークンを作成
                new_token_id = self.create_token(
                    user_id=token_info.user_id,
                    permissions=token_info.permissions,
                    expires_in_hours=24
                )
                new_tokens.append(new_token_id)
                
                # 古いトークンを無効化
                self.revoke_token(token_info.token_id)
        
        return new_tokens
    
    def get_token_usage_stats(self, days: int = 30) -> Dict:
        """トークン使用統計を取得"""
        now = datetime.utcnow()
        cutoff_date = now - timedelta(days=days)
        
        usage_stats = {
            'total_usage': 0,
            'unique_users': set(),
            'daily_usage': {},
            'token_types': {}
        }
        
        for token_info in self._tokens.values():
            if token_info.last_used and token_info.last_used >= cutoff_date:
                usage_stats['total_usage'] += 1
                usage_stats['unique_users'].add(token_info.user_id)
                
                # 日別使用統計
                date_key = token_info.last_used.strftime('%Y-%m-%d')
                usage_stats['daily_usage'][date_key] = usage_stats['daily_usage'].get(date_key, 0) + 1
                
                # トークンタイプ統計
                permission_key = ','.join(sorted(token_info.permissions))
                usage_stats['token_types'][permission_key] = usage_stats['token_types'].get(permission_key, 0) + 1
        
        # セットをリストに変換
        usage_stats['unique_users'] = list(usage_stats['unique_users'])
        
        return usage_stats 