"""
Email Reply Parser

A simple library to parse email replies and extract the original message,
removing quoted text, signatures, and reply chains.

Based on the concepts from the GitHub's email_reply_parser library.
"""
import re
from typing import List

class EmailReplyParser:
    """Parser for extracting original content from email replies."""
    
    @classmethod
    def parse_reply(cls, text: str) -> str:
        """
        Extract the original message from an email reply.
        
        Args:
            text: The full email body text
            
        Returns:
            The extracted original message without quoted content
        """
        email = Email(text)
        return email.get_visible_text()
        
    @classmethod
    def read(cls, text: str) -> 'Email':
        """
        Read an email and parse it, returning an Email object.
        
        Args:
            text: The full email body text
            
        Returns:
            Email object representing the parsed email
        """
        return Email(text)


class Email:
    """Email class that represents a parsed email."""
    
    QUOTE_REGEX = re.compile(r'^\s*(>|\|).*$', re.MULTILINE)
    SIG_REGEX = re.compile(r'(--|__|\w+\s*regards|sincerely|thank you|thanks|cheers|best|warm(ly| regards)|yours truly|all the best|best wishes|^sent from)',
                          re.IGNORECASE)
    HEADER_REGEX = re.compile(r'^\s*(from|sent|to|subject|date|cc|bcc):', re.IGNORECASE | re.MULTILINE)
    ORIGINAL_MSG_REGEX = re.compile(r'^\s*(-----\s*Original Message\s*-----|On.*wrote:|\s*--+ Forwarded message --+)', re.IGNORECASE | re.MULTILINE)
    
    def __init__(self, text: str):
        """
        Initialize an Email object from text.
        
        Args:
            text: The email body text
        """
        self.fragments: List[Fragment] = []
        self.fragment_types: List[str] = []
        self.parse_text(text)
        
    def parse_text(self, text: str) -> None:
        """
        Parse the email text into fragments.
        
        Args:
            text: The email body text
        """
        # Normalize line endings
        text = text.replace('\r\n', '\n')
        
        # Split into lines
        lines = text.split('\n')
        fragment = Fragment()
        self.fragments.append(fragment)
        
        for line in lines:
            # Check for quoted text
            if self.QUOTE_REGEX.match(line):
                if fragment.is_quoted == False and fragment.content:
                    # Start a new quoted fragment
                    fragment = Fragment(is_quoted=True)
                    self.fragments.append(fragment)
                fragment.is_quoted = True
                fragment.content.append(line)
                continue
                
            # Check for original message marker or reply header
            if self.ORIGINAL_MSG_REGEX.match(line) or self.HEADER_REGEX.match(line):
                if not fragment.is_quoted and fragment.content:
                    # Start a new fragment for headers/quoted
                    fragment = Fragment(is_quoted=True)
                    self.fragments.append(fragment)
                fragment.is_quoted = True
                fragment.content.append(line)
                continue
                
            # Check for signature marker
            if self.SIG_REGEX.match(line) and not fragment.is_quoted:
                # If we find a signature marker in non-quoted text, consider everything below a signature
                if fragment.content:
                    # Start a new fragment for the signature
                    fragment = Fragment(is_signature=True)
                    self.fragments.append(fragment)
                fragment.is_signature = True
                fragment.content.append(line)
                continue
                
            # Regular content - add to the current fragment
            if (fragment.is_quoted or fragment.is_signature) and not line.strip():
                # Start a new regular fragment for non-quoted content
                fragment = Fragment()
                self.fragments.append(fragment)
            fragment.content.append(line)
            
    def get_visible_text(self) -> str:
        """
        Get the visible text from the email, stripping quoted content and signatures.
        
        Returns:
            A string with only the original content
        """
        visible_text = []
        for fragment in self.fragments:
            if not fragment.is_quoted and not fragment.is_signature and fragment.content:
                visible_text.append('\n'.join(fragment.content))
                
        return '\n'.join(visible_text).strip()
        
    def get_fragments(self) -> List['Fragment']:
        """
        Get all fragments from the email.
        
        Returns:
            List of Fragment objects
        """
        return self.fragments


class Fragment:
    """A fragment of an email message."""
    
    def __init__(self, is_quoted: bool = False, is_signature: bool = False):
        """
        Initialize a Fragment object.
        
        Args:
            is_quoted: Whether this fragment is a quoted text
            is_signature: Whether this fragment is a signature
        """
        self.content: List[str] = []
        self.is_quoted = is_quoted
        self.is_signature = is_signature
        
    def __str__(self) -> str:
        """String representation of the fragment."""
        return '\n'.join(self.content)


if __name__ == "__main__":
    # Example usage
    test_email = """
Hello,

This is the original message content that we want to keep.

> On Mon, Aug 26, 2025 at 3:24 PM Some Person <person@example.com> wrote:
> This is quoted text that should be removed.
> 
> Another line of quoted text.

Some more original content.

Thanks,
Your Name
"""
    
    parsed = EmailReplyParser.parse_reply(test_email)
    print("Parsed result:\n", parsed)
