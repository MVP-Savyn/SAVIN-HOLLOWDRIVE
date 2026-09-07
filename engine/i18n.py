import os
import json
import logging

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALES_DIR = os.path.join(ENGINE_DIR, 'locales')
ROOT_DIR = os.path.dirname(ENGINE_DIR)
CONFIG_FILE = os.path.join(ROOT_DIR, 'config.json')

_catalogs = {}
_current_lang = 'es'

LANGUAGE_NAMES = {
    'es': 'Español',
    'en': 'English',
    'zh': '简体中文',
    'ja': '日本語',
    'ru': 'Русский',
    'pt': 'Português',
    'de': 'Deutsch',
    'fr': 'Français',
    'it': 'Italiano',
    'ko': '한국어'
}

def load_locales():
    global _catalogs
    _catalogs = {}
    if not os.path.exists(LOCALES_DIR):
        os.makedirs(LOCALES_DIR, exist_ok=True)
        
    for fname in os.listdir(LOCALES_DIR):
        if fname.endswith('.json'):
            lang_code = fname[:-5].lower()
            fpath = os.path.join(LOCALES_DIR, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    _catalogs[lang_code] = json.load(f)
            except Exception as e:
                logging.error(f'Error cargando catálogo de idioma {fname}: {e}')

def get_available_languages():
    if not _catalogs:
        load_locales()
    langs = []
    for code in _catalogs.keys():
        name = LANGUAGE_NAMES.get(code, code.upper())
        langs.append({
            'code': code,
            'name': name,
            'display': f'🌐 {name}'
        })
    # Prioritize languages order: Spanish first, English second, followed by other major languages
    order = {
        'es': 0,
        'en': 1,
        'zh': 2,
        'ja': 3,
        'ru': 4,
        'pt': 5,
        'de': 6,
        'fr': 7,
        'it': 8,
        'ko': 9
    }
    langs.sort(key=lambda x: order.get(x['code'], 99))
    return langs

def get_saved_language():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                return cfg.get('idioma', 'es')
    except Exception:
        pass
    return 'es'

def save_language(lang_code):
    try:
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        cfg['idioma'] = lang_code
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f'Error guardando preferencia de idioma en config.json: {e}')

def set_current_language(lang_code):
    global _current_lang
    if not _catalogs:
        load_locales()
    if lang_code in _catalogs:
        _current_lang = lang_code
        save_language(lang_code)
        return True
    return False

def get_current_language():
    return _current_lang

def t(key, default=None, **kwargs):
    global _current_lang
    if not _catalogs:
        load_locales()
        
    parts = key.split('.')
    
    # Try current language
    val = _catalogs.get(_current_lang)
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            val = None
            break
            
    # Fallback to Spanish if missing
    if val is None and _current_lang != 'es':
        val = _catalogs.get('es')
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                val = None
                break

    # Fallback to English if still missing
    if val is None and _current_lang != 'en':
        val = _catalogs.get('en')
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                val = None
                break

    if val is None:
        val = default if default is not None else key

    if isinstance(val, str) and kwargs:
        try:
            return val.format(**kwargs)
        except Exception:
            return val
    return val

# Initialize on import
load_locales()
_current_lang = get_saved_language()
