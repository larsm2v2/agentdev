#!/usr/bin/env python3
"""
Test the email_reply_parser functionality
"""
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gmail.email_reply_parser import EmailReplyParser

def test_simple_reply():
    """Test parsing a simple reply with quote"""
    email_text = """
Hello,

This is my response to your inquiry.

> On Tue, Aug 25, 2025 at 2:15 PM Original Sender <sender@example.com> wrote:
> What is the status of the project?
> 
> Regards,
> Original Sender

Let me know if you need anything else.

Best,
Responder
"""
    parsed = EmailReplyParser.parse_reply(email_text)
    print("\n--- ORIGINAL EMAIL ---")
    print(email_text)
    print("\n--- PARSED RESULT ---")
    print(parsed)
    
    # This should include "Hello", "This is my response", and "Let me know" parts
    # but exclude the quoted text and signature

def test_complex_reply():
    """Test parsing a more complex reply with multiple quotes and signatures"""
    email_text = """
Thank you for your response.

I will review the proposal and get back to you tomorrow.

> On Mon, Aug 24, 2025 at 11:30 AM Jane Smith <jane@example.com> wrote:
> Here's the updated proposal as we discussed.
>
> > On Fri, Aug 21, 2025, John Doe <john@example.com> wrote:
> > Can you please send me the latest version of the proposal?
> > 
> > Thanks,
> > John
> 
> Let me know if you need any clarification.
>
> Best regards,
> Jane Smith
> Marketing Director
> Example Corp.

Sincerely,
Robert Johnson
Project Manager
"""
    parsed = EmailReplyParser.parse_reply(email_text)
    print("\n--- ORIGINAL EMAIL ---")
    print(email_text)
    print("\n--- PARSED RESULT ---")
    print(parsed)
    
    # This should include only "Thank you" and "I will review" parts

def test_forwarded_email():
    """Test parsing a forwarded email"""
    email_text = """
Please see the message below from the client.

------ Forwarded message ------
From: Client <client@example.com>
Date: Tue, Aug 26, 2025 at 9:45 AM
Subject: Project Requirements
To: sales@ourcompany.com

We need to implement the following features:
1. User authentication
2. Payment processing
3. Reporting dashboard

Please provide a quote by the end of this week.

Regards,
Client
"""
    parsed = EmailReplyParser.parse_reply(email_text)
    print("\n--- ORIGINAL EMAIL ---")
    print(email_text)
    print("\n--- PARSED RESULT ---")
    print(parsed)
    
    # This should include only "Please see the message below from the client."

def test_multi_level_reply():
    """Test parsing a multi-level reply chain"""
    email_text = """
Yes, I'm available for a call tomorrow at 2pm.

On Wed, Aug 27, 2025 at 10:05 AM Meeting Scheduler <scheduler@example.com> wrote:
> Hello team,
> 
> Are you available for a project kickoff call tomorrow at 2pm?
> 
> > On Tue, Aug 26, 2025 at 4:30 PM Project Manager <pm@example.com> wrote:
> > We need to schedule the kickoff call this week.
> > 
> > Thanks,
> > PM
> 
> Best,
> Scheduler

Thanks,
Team Member
"""
    parsed = EmailReplyParser.parse_reply(email_text)
    print("\n--- ORIGINAL EMAIL ---")
    print(email_text)
    print("\n--- PARSED RESULT ---")
    print(parsed)
    
    # This should include only "Yes, I'm available" and possibly the thanks

if __name__ == "__main__":
    print("=== TESTING EMAIL REPLY PARSER ===")
    test_simple_reply()
    test_complex_reply()
    test_forwarded_email()
    test_multi_level_reply()
    print("\nTests completed!")
