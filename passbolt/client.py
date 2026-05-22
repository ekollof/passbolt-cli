from __future__ import annotations

"""Passbolt API client"""

import json
import requests
from typing import Any
from urllib.parse import urljoin

from passbolt.config import PassboltConfig
from passbolt.auth import PassboltAuth


class PassboltClient:
    """Client for interacting with Passbolt API"""
    
    def __init__(self, config: PassboltConfig) -> None:
        self.config: PassboltConfig = config
        self.base_url: str = config.server_url
        self.auth: PassboltAuth = PassboltAuth(config)
        self.session: requests.Session
        
        # Authenticate and get authenticated session
        self._authenticate()
    
    def _authenticate(self) -> None:
        """Authenticate with Passbolt API using GPG key"""
        try:
            self.session = self.auth.get_auth_token()
            self.session.headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            })
        except Exception as e:
            raise Exception(f"Authentication failed: {e}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an authenticated request to the API"""
        url = urljoin(self.base_url, endpoint)
        response = self.session.request(method, url, **kwargs)
        
        # Handle session expiration
        match response.status_code:
            case 401 | 403:
                # Re-authenticate
                self._authenticate()
                # Retry request
                response = self.session.request(method, url, **kwargs)
        
        response.raise_for_status()
        return response
    
    def get_resources(self, filter_query: str | None = None) -> list[dict[str, Any]]:
        """Get list of password resources"""
        endpoint = '/resources.json'
        
        params = {}
        if filter_query:
            params['filter[search]'] = filter_query
        
        response = self._make_request('GET', endpoint, params=params)
        data = response.json()
        
        # Passbolt API returns data in 'body' or directly
        if isinstance(data, dict) and 'body' in data:
            return data['body']
        return data if isinstance(data, list) else []
    
    def get_resource_by_id(self, resource_id: str) -> dict[str, Any]:
        """Get a specific resource by ID"""
        endpoint = f'/resources/{resource_id}.json'
        response = self._make_request('GET', endpoint)
        data = response.json()
        
        if isinstance(data, dict) and 'body' in data:
            return data['body']
        return data
    
    def get_secret(self, resource_id: str) -> str:
        """Get the decrypted secret for a resource"""
        endpoint = f'/secrets/resource/{resource_id}.json'
        response = self._make_request('GET', endpoint)
        data = response.json()
        
        # Extract encrypted secret
        if isinstance(data, dict) and 'body' in data:
            encrypted_data = data['body']['data']
        elif isinstance(data, dict) and 'data' in data:
            encrypted_data = data['data']
        else:
            encrypted_data = data
        
        # Decrypt using GPG
        decrypted = self.auth.decrypt_secret(encrypted_data)
        return decrypted
    
    def search_resources(self, query: str) -> list[dict[str, Any]]:
        """Search for resources matching query"""
        # Try server-side filtering first
        resources = self.get_resources(filter_query=query)
        
        # If no filter was applied server-side (all results returned),
        # do client-side filtering
        if query:
            query_lower = query.lower()
            filtered = []
            for resource in resources:
                # Search in name, username, uri, and description
                name = (resource.get('name') or '').lower()
                username = (resource.get('username') or '').lower()
                uri = (resource.get('uri') or '').lower()
                description = (resource.get('description') or '').lower()
                
                if (query_lower in name or 
                    query_lower in username or 
                    query_lower in uri or 
                    query_lower in description):
                    filtered.append(resource)
            
            return filtered
        
        return resources
    
    def find_resource_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a resource by exact or partial name match"""
        resources = self.get_resources()
        
        # Try exact match first
        for resource in resources:
            if resource.get('name', '').lower() == name.lower():
                return resource
        
        # Try partial match
        matches = [r for r in resources if name.lower() in r.get('name', '').lower()]
        
        match len(matches):
            case 1:
                return matches[0]
            case n if n > 1:
                # Multiple matches, raise error with suggestions
                names = [r['name'] for r in matches[:5]]
                raise ValueError(f"Multiple resources match '{name}': {', '.join(names)}")
        
        return None
    
    def find_resource_by_name_or_id(self, identifier: str) -> dict[str, Any] | None:
        """Find a resource by UUID or name"""
        # Check if it looks like a UUID (contains hyphens and is 36 chars)
        if len(identifier) == 36 and identifier.count('-') == 4:
            # Try to fetch by ID directly
            try:
                return self.get_resource_by_id(identifier)
            except Exception:
                pass
        
        # Fall back to name search
        return self.find_resource_by_name(identifier)
