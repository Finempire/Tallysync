import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client

def debug_login():
    c = Client()
    
    # Try with localhost
    print("--- Attempt 1: localhost ---")
    response = c.post(
        '/api/v1/auth/login/',
        data={'email': 'admin@tallysync.com', 'password': 'admin'},
        content_type='application/json',
        HTTP_HOST='localhost:8000'
    )
    print(f"Status: {response.status_code}")
    print(f"Content: {response.content.decode()}")

    # Try with 127.0.0.1
    print("\n--- Attempt 2: 127.0.0.1 ---")
    response = c.post(
        '/api/v1/auth/login/',
        data={'email': 'admin@tallysync.com', 'password': 'admin'},
        content_type='application/json',
        HTTP_HOST='127.0.0.1:8000'
    )
    print(f"Status: {response.status_code}")
    content = response.content.decode()
    print(f"Content: {content}")
    
    if response.status_code == 200:
        token = json.loads(content)['access']
        print("\n--- Attempt 4: Profile & Ping ---")
        
        # Test Ping
        resp_ping = c.get('/ping/', HTTP_HOST='127.0.0.1:8000')
        print(f"Ping Status: {resp_ping.status_code}")
        
        # Test Profile
        resp_profile = c.get(
            '/api/v1/auth/profile/',
            HTTP_AUTHORIZATION=f'Bearer {token}',
            HTTP_HOST='127.0.0.1:8000'
        )
        print(f"Profile Status: {resp_profile.status_code}")
        print(f"Profile Content: {resp_profile.content.decode()}")

    # Try with username instead of email key
    print("\n--- Attempt 3: username key ---")
    response = c.post(
        '/api/v1/auth/login/',
        data={'username': 'admin@tallysync.com', 'password': 'admin'},
        content_type='application/json',
        HTTP_HOST='localhost:8000'
    )
    print(f"Status: {response.status_code}")
    print(f"Content: {response.content.decode()}")


if __name__ == "__main__":
    debug_login()
