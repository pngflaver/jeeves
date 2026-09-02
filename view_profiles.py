#!/usr/bin/env python3
"""
Private Server-Side User Profile Inspector
Run directly from terminal:
    python3 view_profiles.py
    python3 view_profiles.py --user <user_id_or_username>
    python3 view_profiles.py --assess
"""

import sys
import argparse
from services.profile_service import profile_service

def main():
    parser = argparse.ArgumentParser(description="Private User Profile & Rudeness Inspector")
    parser.add_argument("--user", help="Lookup specific user by ID or username", default=None)
    parser.add_argument("--assess", action="store_true", help="Trigger a full profile reassessment now")
    args = parser.parse_args()

    if args.assess:
        print("🔄 Running full assessment across all user profiles...")
        res = profile_service.assess_all_users()
        print(f"✅ Assessment complete. Total evaluated: {res['total_assessed']}")

    if args.user:
        profile = profile_service.find_user_profile(args.user)
        if not profile:
            print(f"❌ No profile found for '{args.user}'.")
            sys.exit(1)

        ass = profile.get("assessment", {})
        print("=" * 65)
        print(f"👤 USER PROFILE: {profile.get('full_name')} (@{profile.get('username')})")
        print("=" * 65)
        print(f"• User ID:         {profile.get('user_id')}")
        print(f"• Total Messages:  {profile.get('total_messages')} (Rude: {profile.get('rude_message_count')}, Tech: {profile.get('technical_message_count')})")
        print(f"• First Seen:      {profile.get('first_seen')[:19]}")
        print(f"• Last Seen:       {profile.get('last_seen')[:19]}")
        print("-" * 65)
        print(f"📊 BEHAVIORAL ASSESSMENT:")
        print(f"• Archetype:       {ass.get('archetype')}")
        print(f"• Tone:            {ass.get('tone')}")
        print(f"• Rudeness Rating: {ass.get('rudeness_score')}/10")
        print(f"• Key Traits:      {', '.join(ass.get('traits', []))}")
        print(f"• Frequent Topics: {', '.join(ass.get('topics', []))}")
        print(f"• Summary:         {ass.get('summary')}")
        print("-" * 65)
        print("💬 Recent Messages:")
        for idx, m in enumerate(profile.get("message_history", [])[-10:], 1):
            flag = " [🚨 RUDE/PROVOCATIVE]" if m.get("is_rude") else ""
            print(f"  {idx}. [{m.get('timestamp')[:19]}]{flag}: {m.get('text')}")
        print("=" * 65)
        return

    # Default: Show summary roster
    summaries = profile_service.get_all_profiles_summary()
    print("=" * 75)
    print(f"👥 PRIVATE USER PROFILES ROSTER ({len(summaries)} users tracked)")
    print("=" * 75)
    if not summaries:
        print("No user profiles recorded yet.")
        return

    print(f"{'User ID':<15} {'Username':<18} {'Archetype':<25} {'Rude/10':<8} {'Msgs':<6}")
    print("-" * 75)
    for s in summaries:
        print(f"{s['user_id']:<15} @{s['username']:<17} {s['archetype']:<25} {s['rudeness_score']:<8} {s['total_messages']:<6}")
    print("=" * 75)
    print("💡 Run 'python3 view_profiles.py --user <user_id_or_username>' for detailed breakdown.")

if __name__ == "__main__":
    main()
