
def _guess_format_by_extension(filename):
    extension = filename.lower().split('.')[-1]
    
    format_mapping = {
        'json': 'JSON',
        'xml': 'XML',
        'yaml': 'YAML',
        'yml': 'YAML',
        'csv': 'CSV',
        'txt': 'Plain Text',
        'bin': 'Binary',
        # 可以添加更多扩展名映射
    }
    
    return format_mapping.get(extension, 'Unknown')


def _is_plain_text(filename, content = None):
    fotmat = _guess_format_by_extension(filename)
    if fotmat == 'Plain Text':
        return True
    return False