import re
import string
import tiktoken

class TextProcessing:

    @staticmethod
    def tiktoken_len(document):
        tokenizer = tiktoken.encoding_for_model('text-embedding-ada-002')
        tokens = tokenizer.encode(
            document,
            disallowed_special=()
        )
        return len(tokens)
    
    @staticmethod
    def strip_excess_whitespace(text):
        
        # Defines which chars can be kept; Alpha-numeric chars, punctionation, and whitespaces.
        # Remove bad chars
        text = re.sub(f'[^{re.escape(string.printable)}]', '', text)
        # Reduces any sequential occurrences of a specific whitespace (' \t\n\r\v\f') to just two of those specific whitespaces
        # Create a dictionary to map each whitespace character to its escape sequence (if needed)
        whitespace_characters = {
            ' ': r' ',
            '\t': r'\t',
            '\n': r'\n',
            '\r': r'\r',
            '\v': r'\v',
            '\f': r'\f',
        }
        # Replace any sequential occurrences of each whitespace characters greater than 3 with just two
        for char, escape_sequence in whitespace_characters.items():
            pattern = escape_sequence + "{3,}"
            replacement = char * 2
            text = re.sub(pattern, replacement, text)
            
        text = text.strip()
        
        return text
    
    @staticmethod
    def remove_all_white_space_except_space(text):
        # Remove all whitespace characters (like \n, \r, \t, \f, \v) except space (' ')
        text = re.sub(r'[\n\r\t\f\v]+', '', text)
        # Remove any extra spaces
        text = re.sub(r' +', ' ', text)
        # Remove leading and trailing spaces
        text = text.strip()
        return text
    
    