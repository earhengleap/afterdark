import httpx
import json
import os
import time
import argparse
from typing import Optional, List, Dict, Set


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
                cookies[name.lower()] = value
    return cookies


def save_progress(username: str, users: List[str], json_data: List[Dict], cursor: Optional[str]) -> None:
    """Save current scraped user list and the cursor point."""
    txt_file = f"{username}_following.txt"
    json_file = f"{username}_following.json"
    state_file = f"{username}_state.json"
    
    # Save text list
    with open(txt_file, 'w', encoding='utf-8') as f:
        for user in users:
            f.write(f"@{user}\nhttps://twitter.com/{user}\n\n")
            
    # Save structured JSON
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
        
    # Save the exact cursor state so we can resume later if needed
    if cursor:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump({"cursor": cursor, "total_saved": len(users)}, f)
    elif os.path.exists(state_file):
        os.remove(state_file) # Done, no state needed


def load_progress(username: str) -> tuple[List[str], List[Dict], Optional[str]]:
    """Try to load a previous scraping session."""
    json_file = f"{username}_following.json"
    state_file = f"{username}_state.json"
    
    users = []
    json_data = []
    cursor = None
    
    if os.path.exists(json_file) and os.path.exists(state_file):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                users = [item["username"] for item in json_data]
                
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                cursor = state.get("cursor")
                
            print(f"Resuming previous session! Found {len(users)} users already saved.")
        except Exception as e:
            print(f"Could not load previous state ({e}). Starting fresh.")
            users, json_data, cursor = [], [], None
            
    return users, json_data, cursor


def get_following_list(username: str, cookies: Dict[str, str], resume: bool = True) -> Optional[List[str]]:
    """Get following list using Twitter GraphQL API with smart rate limits & checkpointing."""

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
        user_variables = {"screen_name": username, "withSafetyModeUserFields": True}
        user_features = {
            "hidden_profile_likes_enabled": True, "hidden_profile_subscriptions_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True, "verified_phone_label_enabled": False,
            "subscriptions_verification_info_is_identity_verified_enabled": True, "subscriptions_verification_info_verified_since_enabled": True,
            "highlights_tweets_tab_ui_enabled": True, "responsive_web_twitter_article_notes_tab_enabled": True,
            "creator_subscriptions_tweet_preview_api_enabled": True, "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True
        }

        user_params = {'variables': json.dumps(user_variables), 'features': json.dumps(user_features)}
        user_response = client.get(user_url, params=user_params)

        if user_response.status_code != 200:
            print(f"Error: Status {user_response.status_code}")
            return None

        user_data = user_response.json()
        
        # Immediate check if the account is protected
        try:
            legacy_data = user_data['data']['user']['result']['legacy']
            is_protected = legacy_data.get('protected', False)
            if is_protected:
                print(f"\n🛑 Error: The account '@{username}' is Protected (Private)!")
                print("You cannot scrape their following list unless your cookie account is approved to follow them.")
                return None
        except (KeyError, TypeError):
            pass # Failsafe if the API structure changes
            
        user_id = user_data['data']['user']['result']['rest_id']
        print(f"Found {username}'s Internal ID: {user_id}")

        # Get following list
        following_url = "https://api.twitter.com/graphql/iSicc7LrzWGBgDPL0tM_TQ/Following"
        
        # Load state
        following_list, following_json, cursor = [], [], None
        if resume:
            following_list, following_json, cursor = load_progress(username)
            
        seen_users: Set[str] = set(following_list)
        count = len(following_list)
        max_retries = 3
        page_num = 0

        print(f"Fetching following list... (starting at page {page_num+1})")

        while True:
            page_num += 1
            variables = {
                "userId": user_id,
                "count": 100,
                "includePromotedContent": False
            }
            if cursor:
                variables["cursor"] = cursor

            following_features = {
                "rweb_tipjar_consumption_enabled": True, "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False, "creator_subscriptions_tweet_preview_api_enabled": True,
                "responsive_web_graphql_timeline_navigation_enabled": True, "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "communities_web_enable_tweet_community_results_fetch": True, "c9s_tweet_anatomy_moderator_badge_enabled": True,
                "articles_preview_enabled": True, "responsive_web_media_download_video_enabled": True,
                "tweetypie_unmention_optimization_enabled": True, "responsive_web_edit_tweet_api_enabled": True,
                "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True, "view_counts_everywhere_api_enabled": True,
                "longform_notetweets_consumption_enabled": True, "responsive_web_twitter_article_tweet_consumption_enabled": True,
                "tweet_awards_web_tipping_enabled": False, "creator_subscriptions_quote_tweet_preview_enabled": False,
                "freedom_of_speech_not_reach_fetch_enabled": True, "standardized_nudges_misinfo": True,
                "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True, "rweb_video_timestamps_enabled": True,
                "longform_notetweets_rich_text_read_enabled": True, "longform_notetweets_inline_media_enabled": True,
                "responsive_web_enhance_cards_enabled": False
            }

            params = {'variables': json.dumps(variables), 'features': json.dumps(following_features)}

            # Retry logic & Smart Rate Limits
            response = None
            for attempt in range(max_retries):
                try:
                    response = client.get(following_url, params=params)
                    
                    if response.status_code == 429:
                        # SMART RATE LIMIT HANDLING
                        reset_header = response.headers.get('x-rate-limit-reset')
                        if reset_header:
                            reset_time = int(reset_header)
                            wait_time = max(0, reset_time - int(time.time())) + 5 # Add 5s buffer
                            print(f"Twitter Rate Limited! Sleeping for {wait_time} seconds (until {time.strftime('%H:%M:%S', time.localtime(reset_time))})...")
                            time.sleep(wait_time)
                        else:
                            wait_time = 60 * (attempt + 1)
                            print(f"Rate limited (No header info). Waiting {wait_time} seconds...")
                            time.sleep(wait_time)
                        continue
                    
                    if response.status_code != 200:
                        print(f"Error fetching following (page {page_num}): {response.status_code}")
                        return following_list if following_list else None
                    
                    break
                    
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
            users_before = len(following_list)
            next_cursor = None
            found_users = False

            try:
                # Check for private/suspended silent blocking
                user_node = data.get('data', {}).get('user', {})
                if not user_node or 'result' not in user_node:
                    print(f"\nError: Twitter blocked the request! The account '@{username}' is likely Private/Protected or Suspended.")
                    print("You can only scrape private accounts if your cookie account is approved to follow them.")
                    break
                    
                instructions = user_node['result']['timeline']['timeline']['instructions']

                for instruction in instructions:
                    if instruction.get('type') == 'TimelineAddEntries':
                        for entry in instruction.get('entries', []):
                            entry_id = entry.get('entryId', '')
                            
                            if entry_id.startswith('user-'):
                                try:
                                    user_result = entry['content']['itemContent']['user_results']['result']
                                    if user_result.get('__typename') == 'UserUnavailable':
                                        continue
                                    
                                    username_found = user_result.get('legacy', {}).get('screen_name') or user_result.get('screen_name')
                                    if username_found and username_found not in seen_users:
                                        following_list.append(username_found)
                                        following_json.append({
                                            "username": username_found,
                                            "handle": f"@{username_found}",
                                            "url": f"https://twitter.com/{username_found}"
                                        })
                                        seen_users.add(username_found)
                                        count += 1
                                        found_users = True
                                        
                                except (KeyError, TypeError):
                                    continue

                            elif entry_id.startswith('cursor-bottom-'):
                                try:
                                    cursor_value = entry.get('content', {}).get('value')
                                    if cursor_value:
                                        next_cursor = cursor_value
                                except (KeyError, TypeError):
                                    pass

                users_found_this_page = len(following_list) - users_before
                print(f"Page {page_num}: Found {users_found_this_page} new users (Total scraped: {count})")

                # State Saving
                save_progress(username, following_list, following_json, next_cursor)

                if next_cursor is None or next_cursor == cursor or (not found_users and next_cursor):
                    print("Reached the end of the following list!")
                    save_progress(username, following_list, following_json, None) # Clear cursor
                    break
                
                cursor = next_cursor
                time.sleep(1.5) # Anti-ban delay

            except KeyError as e:
                print(f"Error parsing response on page {page_num}: {e}")
                print("Response snippet:", json.dumps(data, indent=2)[:1500])
                break
            except Exception as e:
                print(f"Unexpected error on page {page_num}: {e}")
                break

        return following_list

    except Exception as e:
        print(f"Fatal error: {e}")
        return None
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description="Scrape Twitter/X 'Following' lists safely.")
    parser.add_argument("-u", "--user", type=str, help="The target Twitter username (without @)")
    parser.add_argument("-c", "--cookies", type=str, default="twitter_cookies.txt", help="Path to your twitter_cookies.txt file")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh and ignore any saved checkpoints")
    
    args = parser.parse_args()

    # Create config folder if needed
    os.makedirs('config', exist_ok=True)
    
    cookies_file = args.cookies
    if not os.path.exists(cookies_file):
        print(f"Error: Cookie file not found at {cookies_file}")
        return

    cookies = parse_cookies(cookies_file)
    if not cookies.get('auth_token') or not cookies.get('ct0'):
        print("Error: Missing 'auth_token' or 'ct0' inside cookies file. Did you log out?")
        return

    print("Cookies loaded successfully")

    target_username = args.user
    if not target_username:
        target_username = input("\nEnter Twitter username (without @): ").strip()

    if not target_username:
        print("Username cannot be empty")
        return

    try:
        get_following_list(target_username, cookies, resume=not args.no_resume)
        print("\nScraping Completed!")
    except KeyboardInterrupt:
        print("\nScript aborted by user. Don't worry, your progress has been saved automatically!")


if __name__ == "__main__":
    main()