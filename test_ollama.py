#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify Ollama connectivity and AI title generation.
Run this to check if your Ollama setup is working correctly.
"""

import json
import urllib.request
import sys

OLLAMA_URL = "http://127.0.0.1:11434"

def test_ollama_connection():
    """Test if Ollama is running and accessible."""
    print("[*] Testing Ollama connection...")
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as response:
            data = json.loads(response.read())
            models = data.get("models", [])
            print(f"[OK] Ollama is running! Found {len(models)} models:")
            for model in models:
                name = model.get("name", "unknown")
                size_gb = model.get("size", 0) / (1024**3)
                print(f"   - {name} ({size_gb:.2f} GB)")
            return True
    except Exception as e:
        print(f"[FAIL] Cannot connect to Ollama: {e}")
        print(f"   Make sure Ollama is running on {OLLAMA_URL}")
        return False

def check_required_models():
    """Check if required models are installed."""
    print("\n[*] Checking required models...")
    required = {
        "moondream:latest": "Vision model for image/video analysis",
        "dolphin-llama3:8b": "Text model for title polishing",
        "gemma3:4b": "Fallback text model"
    }
    
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as response:
            data = json.loads(response.read())
            installed = {model.get("name") for model in data.get("models", [])}
            
            all_present = True
            for model_name, description in required.items():
                if model_name in installed:
                    print(f"[OK] {model_name} - {description}")
                else:
                    print(f"[MISSING] {model_name} - {description}")
                    print(f"   Install with: ollama pull {model_name}")
                    all_present = False
            
            return all_present
    except Exception as e:
        print(f"[FAIL] Error checking models: {e}")
        return False

def test_vision_model():
    """Test the vision model with a simple prompt."""
    print("\n[*] Testing vision model (moondream)...")
    try:
        # Simple test without image
        payload = {
            "model": "moondream:latest",
            "prompt": "Test prompt",
            "stream": False
        }
        
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
            if result.get("error"):
                print(f"[FAIL] Model error: {result.get('error')}")
                return False
            print(f"[OK] Vision model is working!")
            return True
    except Exception as e:
        print(f"[FAIL] Vision model test failed: {e}")
        return False

def test_text_model():
    """Test the text model with a simple prompt."""
    print("\n[*] Testing text model (dolphin-llama3)...")
    try:
        payload = {
            "model": "dolphin-llama3:8b",
            "prompt": "Say 'AI is working' in 3 words",
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 10}
        }
        
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
            if result.get("error"):
                print(f"[FAIL] Model error: {result.get('error')}")
                return False
            response_text = result.get("response", "").strip()
            print(f"[OK] Text model is working! Response: {response_text}")
            return True
    except Exception as e:
        print(f"[FAIL] Text model test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Ollama AI Title Generation - System Check")
    print("=" * 60)
    
    tests_passed = 0
    tests_total = 4
    
    if test_ollama_connection():
        tests_passed += 1
    
    if check_required_models():
        tests_passed += 1
    
    if test_vision_model():
        tests_passed += 1
    
    if test_text_model():
        tests_passed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {tests_passed}/{tests_total} tests passed")
    print("=" * 60)
    
    if tests_passed == tests_total:
        print("\n[SUCCESS] All tests passed! Your AI title generation system is ready.")
        print("\nNext steps:")
        print("1. Start the Mini App server: python telegram-bot-websites/server.py")
        print("2. Watch the logs for 'AI title worker active'")
        print("3. Post new media to your Telegram group")
        print("4. Check the website for AI-generated titles")
        return 0
    else:
        print("\n[WARNING] Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("- Start Ollama: ollama serve")
        print("- Install missing models: ollama pull <model-name>")
        return 1

if __name__ == "__main__":
    sys.exit(main())
