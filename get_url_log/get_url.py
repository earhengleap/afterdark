import json
import re
from datetime import datetime

def extract_urls_from_log(log_file_path):
    """
    Extract URLs from download_log.log and categorize them
    """
    profile_urls = []
    video_urls = []
    
    try:
        with open(log_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
            # Extract URLs from JSON objects
            json_objects = re.findall(r'\{[^{}]*\}[^{}]*', content)
            
            for json_str in json_objects:
                try:
                    data = json.loads(json_str)
                    if 'url' in data and data['url'].startswith('http'):
                        url = data['url']
                        # Check if it's a video URL (contains /status/)
                        if '/status/' in url:
                            video_urls.append(url)
                            # ALSO extract profile URL from video URL
                            profile_match = re.search(r'(https://x\.com/[^/]+)', url)
                            if profile_match:
                                profile_url = profile_match.group(1)
                                if profile_url not in profile_urls:
                                    profile_urls.append(profile_url)
                        else:
                            # It's already a profile URL
                            profile_urls.append(url)
                            
                    # Also extract from username field if available
                    if 'username' in data and data['username']:
                        username = data['username']
                        profile_url = f"https://x.com/{username}"
                        if profile_url not in profile_urls:
                            profile_urls.append(profile_url)
                            
                except json.JSONDecodeError:
                    url_match = re.search(r'"url":\s*"([^"]*)"', json_str)
                    if url_match and url_match.group(1).startswith('http'):
                        url = url_match.group(1)
                        if '/status/' in url:
                            video_urls.append(url)
                            # Extract profile URL from video URL
                            profile_match = re.search(r'(https://x\.com/[^/]+)', url)
                            if profile_match:
                                profile_url = profile_match.group(1)
                                if profile_url not in profile_urls:
                                    profile_urls.append(profile_url)
                        else:
                            profile_urls.append(url)
            
            # Alternative method if no URLs found
            if not profile_urls and not video_urls:
                url_pattern = r'"url":\s*"([^"]*)"'
                url_matches = re.findall(url_pattern, content)
                for url in url_matches:
                    if url.startswith('http'):
                        if '/status/' in url:
                            video_urls.append(url)
                            # Extract profile URL from video URL
                            profile_match = re.search(r'(https://x\.com/[^/]+)', url)
                            if profile_match:
                                profile_url = profile_match.group(1)
                                if profile_url not in profile_urls:
                                    profile_urls.append(profile_url)
                        else:
                            profile_urls.append(url)
        
        # Remove duplicates while preserving order
        def remove_duplicates(url_list):
            seen = set()
            unique = []
            for url in url_list:
                if url not in seen:
                    seen.add(url)
                    unique.append(url)
            return unique
        
        profile_urls = remove_duplicates(profile_urls)
        video_urls = remove_duplicates(video_urls)
        
        return profile_urls, video_urls
        
    except FileNotFoundError:
        print(f"❌ Error: File '{log_file_path}' not found.")
        return [], []
    except Exception as e:
        print(f"❌ Error: {e}")
        return [], []

def create_beautiful_html(profile_urls, video_urls, output_file_path):
    """
    Create a beautiful HTML file with categorized links
    """
    total_links = len(profile_urls) + len(video_urls)
    
    with open(output_file_path, 'w', encoding='utf-8') as output_file:
        output_file.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>X/Twitter Links Manager</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
            padding: 30px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .x-logo {
            font-size: 4rem;
            margin-bottom: 10px;
            text-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 300;
        }
        
        .stats {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 20px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.2);
            padding: 15px 25px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        .stat-number {
            font-size: 2rem;
            font-weight: bold;
            display: block;
        }
        
        .stat-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }
        
        .content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }
        
        @media (max-width: 768px) {
            .content {
                grid-template-columns: 1fr;
            }
        }
        
        .section {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .section-header {
            display: flex;
            align-items: center;
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .section-icon {
            font-size: 2rem;
            margin-right: 15px;
        }
        
        .section-title {
            font-size: 1.5rem;
            color: #1da1f2;
            font-weight: 600;
        }
        
        .section-count {
            background: #1da1f2;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.9rem;
            margin-left: auto;
        }
        
        .links-container {
            max-height: 500px;
            overflow-y: auto;
        }
        
        .link-item {
            padding: 15px;
            margin: 10px 0;
            border: 1px solid #e1e8ed;
            border-radius: 12px;
            background: #f8f9fa;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        
        .link-item:hover {
            background: #e8f4fd;
            border-color: #1da1f2;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(29, 161, 242, 0.2);
        }
        
        .link-username {
            font-weight: 600;
            color: #1da1f2;
            font-size: 1.1rem;
            margin-bottom: 5px;
        }
        
        .profile-url {
            color: #657786;
            font-size: 0.85rem;
            word-break: break-all;
            font-family: 'Courier New', monospace;
            background: #f8f9fa;
            padding: 8px;
            border-radius: 6px;
            border: 1px solid #e1e8ed;
            margin-bottom: 10px;
        }
        
        .link-url {
            color: #657786;
            font-size: 0.85rem;
            word-break: break-all;
            font-family: 'Courier New', monospace;
            background: #f8f9fa;
            padding: 8px;
            border-radius: 6px;
            border: 1px solid #e1e8ed;
        }
        
        .link-actions {
            margin-top: 10px;
            display: flex;
            gap: 10px;
        }
        
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-primary {
            background: #1da1f2;
            color: white;
        }
        
        .btn-primary:hover {
            background: #0d8bd9;
            transform: translateY(-1px);
        }
        
        .btn-secondary {
            background: #f0f0f0;
            color: #333;
        }
        
        .btn-secondary:hover {
            background: #e0e0e0;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #657786;
        }
        
        .empty-state .icon {
            font-size: 3rem;
            margin-bottom: 15px;
            opacity: 0.5;
        }
        
        .footer {
            text-align: center;
            color: white;
            opacity: 0.8;
            font-size: 0.9rem;
            margin-top: 40px;
        }
        
        /* Custom scrollbar */
        .links-container::-webkit-scrollbar {
            width: 6px;
        }
        
        .links-container::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 10px;
        }
        
        .links-container::-webkit-scrollbar-thumb {
            background: #1da1f2;
            border-radius: 10px;
        }
        
        .links-container::-webkit-scrollbar-thumb:hover {
            background: #0d8bd9;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="x-logo">𝕏</div>
            <h1>Twitter Links Manager</h1>
            <p>All your X/Twitter links in one beautiful interface</p>
            <div class="stats">
                <div class="stat-card">
                    <span class="stat-number">''' + str(len(profile_urls)) + '''</span>
                    <span class="stat-label">Profile Links</span>
                </div>
                <div class="stat-card">
                    <span class="stat-number">''' + str(len(video_urls)) + '''</span>
                    <span class="stat-label">Video Links</span>
                </div>
                <div class="stat-card">
                    <span class="stat-number">''' + str(total_links) + '''</span>
                    <span class="stat-label">Total Links</span>
                </div>
            </div>
        </div>
        
        <div class="content">
            <!-- Profile Links Section -->
            <div class="section">
                <div class="section-header">
                    <div class="section-icon">👤</div>
                    <div class="section-title">Profile Accounts</div>
                    <div class="section-count">''' + str(len(profile_urls)) + '''</div>
                </div>
                <div class="links-container">
''')
        
        # Add profile URLs
        if profile_urls:
            for i, url in enumerate(profile_urls, 1):
                # Extract username for display
                username_match = re.search(r'https://x\.com/([^/?]+)', url)
                if username_match:
                    username = username_match.group(1)
                    display_name = f"@{username}"
                else:
                    display_name = "Profile"
                
                output_file.write(f'''
                    <div class="link-item">
                        <div class="link-username">{display_name}</div>
                        <div class="profile-url">{url}</div>
                        <div class="link-actions">
                            <a href="{url}" target="_blank" class="btn btn-primary">Visit Profile</a>
                            <button class="btn btn-secondary" onclick="copyToClipboard('{url}')">Copy Link</button>
                        </div>
                    </div>
''')
        else:
            output_file.write('''
                    <div class="empty-state">
                        <div class="icon">👤</div>
                        <h3>No Profile Links Found</h3>
                        <p>No profile URLs could be extracted from the log file</p>
                    </div>
''')
        
        output_file.write('''
                </div>
            </div>
            
            <!-- Video Links Section -->
            <div class="section">
                <div class="section-header">
                    <div class="section-icon">🎬</div>
                    <div class="section-title">Video Posts</div>
                    <div class="section-count">''' + str(len(video_urls)) + '''</div>
                </div>
                <div class="links-container">
''')
        
        # Add video URLs
        if video_urls:
            for i, url in enumerate(video_urls, 1):
                username_match = re.search(r'https://x\.com/([^/]+)/status/', url)
                if username_match:
                    username = username_match.group(1)
                    display_name = f"@{username}'s Video"
                else:
                    display_name = "Video Post"
                
                output_file.write(f'''
                    <div class="link-item">
                        <div class="link-username">{display_name}</div>
                        <div class="link-url">{url}</div>
                        <div class="link-actions">
                            <a href="{url}" target="_blank" class="btn btn-primary">Watch Video</a>
                            <button class="btn btn-secondary" onclick="copyToClipboard('{url}')">Copy Link</button>
                        </div>
                    </div>
''')
        else:
            output_file.write('''
                    <div class="empty-state">
                        <div class="icon">🎬</div>
                        <h3>No Video Links Found</h3>
                        <p>Video URLs will appear here when available</p>
                    </div>
''')
        
        output_file.write('''
                </div>
            </div>
        </div>
        
        <div class="footer">
            Generated on ''' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ''' | X/Twitter Links Manager
        </div>
    </div>
    
    <script>
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                // Show temporary notification
                const notification = document.createElement('div');
                notification.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: #1da1f2;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 10px;
                    font-weight: 600;
                    z-index: 1000;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                `;
                notification.textContent = '✓ Link copied!';
                document.body.appendChild(notification);
                
                setTimeout(() => {
                    document.body.removeChild(notification);
                }, 2000);
            });
        }
        
        // Add click animation to link items
        document.addEventListener('DOMContentLoaded', function() {
            const linkItems = document.querySelectorAll('.link-item');
            linkItems.forEach(item => {
                item.addEventListener('click', function(e) {
                    if (!e.target.closest('.btn')) {
                        this.style.transform = 'scale(0.98)';
                        setTimeout(() => {
                            this.style.transform = '';
                        }, 150);
                    }
                });
            });
        });

        // Auto-select profile URLs when clicked
        document.addEventListener('DOMContentLoaded', function() {
            const profileUrls = document.querySelectorAll('.profile-url, .link-url');
            profileUrls.forEach(urlElement => {
                urlElement.addEventListener('click', function() {
                    const range = document.createRange();
                    range.selectNodeContents(this);
                    const selection = window.getSelection();
                    selection.removeAllRanges();
                    selection.addRange(range);
                });
            });
        });
    </script>
</body>
</html>''')

def main():
    """
    Main function to extract URLs and create beautiful HTML
    """
    print("🎨 Creating Beautiful X/Twitter Links Manager...")
    print("=" * 60)
    
    # Extract URLs from log file
    log_file_path = "download_log.log"
    profile_urls, video_urls = extract_urls_from_log(log_file_path)
    
    print(f"✅ Found {len(profile_urls)} profile URLs")
    print(f"✅ Found {len(video_urls)} video URLs")
    
    # Display all profile URLs found
    if profile_urls:
        print("\n📋 Profile URLs Found:")
        for url in profile_urls:
            print(f"   • {url}")
    else:
        print("\n❌ No profile URLs found. Checking log file content...")
        # Let's debug by showing what's in the log file
        try:
            with open(log_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                # Look for any URLs in the content
                all_urls = re.findall(r'https://x\.com/[^\s"\']+', content)
                if all_urls:
                    print("🔍 Found these URLs in log file:")
                    for url in all_urls[:10]:  # Show first 10
                        print(f"   • {url}")
                    if len(all_urls) > 10:
                        print(f"   • ... and {len(all_urls) - 10} more")
        except Exception as e:
            print(f"❌ Could not read log file: {e}")
    
    # Create beautiful HTML file
    output_file_path = "twitter_links_manager.html"
    create_beautiful_html(profile_urls, video_urls, output_file_path)
    
    print(f"\n🎉 Beautiful HTML created: {output_file_path}")
    print("📁 Open the HTML file in your browser to view all links")

if __name__ == "__main__":
    main()