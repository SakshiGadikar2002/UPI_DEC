"""
Script to update existing alert rules with user emails from the users table
Run this to ensure all alert rules have email recipients
"""
import asyncio
import sys
sys.path.insert(0, '.')

from database import get_pool, connect_to_postgres


async def update_alert_rules():
    """Update alert rules without email_recipients to use active user emails"""
    await connect_to_postgres()
    pool = get_pool()
    
    async with pool.acquire() as conn:
        # Get all active user emails
        user_emails = await conn.fetch("""
            SELECT email FROM users WHERE is_active = TRUE
        """)
        
        if not user_emails:
            print("No active users found in database")
            return
        
        emails_list = [user['email'] for user in user_emails]
        emails_str = ','.join(emails_list)
        
        print(f"Found {len(emails_list)} active users:")
        for email in emails_list:
            print(f"  - {email}")
        
        # Update alert rules that don't have email_recipients
        updated = await conn.execute("""
            UPDATE alert_rules
            SET email_recipients = $1
            WHERE email_recipients IS NULL OR email_recipients = ''
        """, emails_str)
        
        print(f"\nUpdated alert rules with user emails")
        
        # Show updated rules
        rules = await conn.fetch("""
            SELECT id, name, email_recipients FROM alert_rules
        """)
        
        print(f"\nCurrent alert rules:")
        for rule in rules:
            print(f"  Rule {rule['id']}: {rule['name']}")
            print(f"    Email recipients: {rule['email_recipients']}")


if __name__ == "__main__":
    asyncio.run(update_alert_rules())

