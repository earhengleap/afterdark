import httpx
import json
import os
import time
from typing import Optional, List, Dict


def parse_cookies(cookies_file: str) -> Dict[str, str]:
    """Parse Netscape cookie file."""
    cookies = {}

    with open(cookies_file, 'r') as f:
        for line in f:
            if line.startswith('#') or line.strip() == '':
                continue

            fields = line.strip().split('\t')
            if len(fields) >= 7:
                name = fields[5]
                value = fields[6]
                cookies[name] = value

    return cookies


def get_following_list(username: str, cookies: Dict[str, str]) -> Optional[List[str]]:
    """Get following list using Twitter GraphQL API."""

    headers = {
        'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
        'x-csrf-token': cookies.get('ct0', ''),
        'x-twitter-active-user': 'yes',
        'x-twitter-auth-type': 'OAuth2Session',
        'x-twitter-client-language': 'en',
        'content-type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'https://twitter.com/{username}/following',
    }

    client = httpx.Client(headers=headers, cookies=cookies, timeout=30.0)

    try:
        # Get user ID
        print(f"Looking up user: {username}")
        user_url = f"https://api.twitter.com/graphql/oUZZZ8Oddwxs8Cd3iW3UEA/UserByScreenName"

        user_variables = {
            "screen_name": username,
            "withSafetyModeUserFields": True
        }

        user_features = {
            "hidden_profile_likes_enabled": True,
            "hidden_profile_subscriptions_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "subscriptions_verification_info_is_identity_verified_enabled": True,
            "subscriptions_verification_info_verified_since_enabled": True,
            "highlights_tweets_tab_ui_enabled": True,
            "responsive_web_twitter_article_notes_tab_enabled": True,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True
        }

        user_params = {
            'variables': json.dumps(user_variables),
            'features': json.dumps(user_features)
        }

        user_response = client.get(user_url, params=user_params)

        if user_response.status_code != 200:
            print(f"Error: Status {user_response.status_code}")
            print(user_response.text[:500])
            return None

        user_data = user_response.json()
        user_id = user_data['data']['user']['result']['rest_id']
        print(f"Found user ID: {user_id}")

        # Get following list
        following_url = "https://api.twitter.com/graphql/iSicc7LrzWGBgDPL0tM_TQ/Following"

        following_list = []
        cursor = None
        count = 0
        max_retries = 3
        page_num = 0

        print("Fetching following list...")

        while True:
            page_num += 1
            variables = {
                "userId": user_id,
                "count": 100,  # Keep at 100 to avoid issues
                "includePromotedContent": False
            }

            if cursor:
                variables["cursor"] = cursor

            following_features = {
                "rweb_tipjar_consumption_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False,
                "creator_subscriptions_tweet_preview_api_enabled": True,
                "responsive_web_graphql_timeline_navigation_enabled": True,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "communities_web_enable_tweet_community_results_fetch": True,
                "c9s_tweet_anatomy_moderator_badge_enabled": True,
                "articles_preview_enabled": True,
                "responsive_web_media_download_video_enabled": True,
                "tweetypie_unmention_optimization_enabled": True,
                "responsive_web_edit_tweet_api_enabled": True,
                "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                "view_counts_everywhere_api_enabled": True,
                "longform_notetweets_consumption_enabled": True,
                "responsive_web_twitter_article_tweet_consumption_enabled": True,
                "tweet_awards_web_tipping_enabled": False,
                "creator_subscriptions_quote_tweet_preview_enabled": False,
                "freedom_of_speech_not_reach_fetch_enabled": True,
                "standardized_nudges_misinfo": True,
                "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
                "rweb_video_timestamps_enabled": True,
                "longform_notetweets_rich_text_read_enabled": True,
                "longform_notetweets_inline_media_enabled": True,
                "responsive_web_enhance_cards_enabled": False
            }

            params = {
                'variables': json.dumps(variables),
                'features': json.dumps(following_features)
            }

            # Retry logic for rate limits
            response = None
            for attempt in range(max_retries):
                try:
                    response = client.get(following_url, params=params)
                    
                    if response.status_code == 429:
                        wait_time = 60 * (attempt + 1)
                        print(f"Rate limited. Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    
                    if response.status_code != 200:
                        print(f"Error fetching following (page {page_num}): {response.status_code}")
                        print(response.text[:500])
                        return following_list if following_list else None
                    
                    break  # Success
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"Request failed, retrying... ({attempt + 1}/{max_retries})")
                        time.sleep(5)
                    else:
                        raise

            if response is None or response.status_code != 200:
                print("Failed to get response after retries")
                break

            data = response.json()

            # Track if we found new users in this iteration
            users_before = len(following_list)
            next_cursor = None
            found_users = False

            try:
                instructions = data['data']['user']['result']['timeline']['timeline']['instructions']

                for instruction in instructions:
                    if instruction.get('type') == 'TimelineAddEntries':
                        entries = instruction.get('entries', [])
                        
                        for entry in entries:
                            entry_id = entry.get('entryId', '')
                            
                            # Extract user entries
                            if entry_id.startswith('user-'):
                                try:
                                    user_result = entry['content']['itemContent']['user_results']['result']
                                    
                                    # Handle suspended/unavailable users
                                    if user_result.get('__typename') == 'UserUnavailable':
                                        continue
                                    
                                    # Handle different response structures
                                    if 'legacy' in user_result:
                                        username_found = user_result['legacy']['screen_name']
                                        following_list.append(username_found)
                                        count += 1
                                        found_users = True
                                    elif 'screen_name' in user_result:
                                        username_found = user_result['screen_name']
                                        following_list.append(username_found)
                                        count += 1
                                        found_users = True
                                except (KeyError, TypeError) as e:
                                    # Silently skip unparseable entries - likely suspended accounts
                                    continue

                            # Extract cursor - ONLY use cursor-bottom
                            elif entry_id.startswith('cursor-bottom-'):
                                try:
                                    cursor_value = entry.get('content', {}).get('value')
                                    if cursor_value:
                                        next_cursor = cursor_value
                                except (KeyError, TypeError):
                                    pass

                users_found_this_page = len(following_list) - users_before
                print(f"Page {page_num}: Found {users_found_this_page} users (Total: {count})")

                # Stop conditions - check if cursor changed
                if next_cursor is None:
                    print("✓ No next cursor found - reached end")
                    break
                
                if next_cursor == cursor:
                    print("✓ Cursor didn't change - reached end")
                    break
                
                if not found_users and next_cursor:
                    print("⚠ No users found but cursor exists - might be end")
                    break
                
                # Update cursor for next iteration
                cursor = next_cursor

                # Small delay to avoid rate limits
                time.sleep(1.5)

            except KeyError as e:
                print(f"Error parsing response on page {page_num}: {e}")
                print("Response structure:", json.dumps(data, indent=2)[:1000])
                # Return what we have so far
                break
            except Exception as e:
                print(f"Unexpected error on page {page_num}: {e}")
                import traceback
                traceback.print_exc()
                break

        # Remove duplicates while preserving order
        seen = set()
        unique_following = []
        for user in following_list:
            if user not in seen:
                seen.add(user)
                unique_following.append(user)

        if len(following_list) != len(unique_following):
            print(f"Removed {len(following_list) - len(unique_following)} duplicate entries")

        return unique_following

    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        client.close()


def main():
    cookies_file = "twitter_cookies.txt"

    os.makedirs('config', exist_ok=True)

    if not os.path.exists(cookies_file):
        print(f"Error: Cookie file not found at {cookies_file}")
        return

    cookies = parse_cookies(cookies_file)

    if not cookies.get('auth_token') or not cookies.get('ct0'):
        print("Error: Missing auth_token or ct0 in cookies")
        return

    print("✓ Cookies loaded successfully")

    target_username = input("\nEnter Twitter username (without @): ").strip()

    if not target_username:
        print("Username cannot be empty")
        return

    following = get_following_list(target_username, cookies)

    if following:
        output_file = f"{target_username}_following.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            for user in following:
                f.write(f"@{user}\n")
                f.write(f"https://twitter.com/{user}\n\n")

        # Also create a JSON file with more structured data
        json_file = f"{target_username}_following.json"
        following_data = [
            {
                "username": user,
                "handle": f"@{user}",
                "url": f"https://twitter.com/{user}"
            }
            for user in following
        ]
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(following_data, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Success! Saved {len(following)} users")
        print(f"  - Text format: '{output_file}'")
        print(f"  - JSON format: '{json_file}'")
        print(f"Total unique users: {len(following)}")
    else:
        print("\n✗ Failed to fetch following list")


if __name__ == "__main__":
    main()