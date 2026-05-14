import tiktoken

def count_tokens(text, model="gpt-4o"):
    """
    סופר טוקנים עבור טקסט גנרי. 
    אם לא ידוע איזה מודל, משתמשים ב-cl100k_base (הסטנדרט של GPT-4).
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    
    return len(encoding.encode(text))