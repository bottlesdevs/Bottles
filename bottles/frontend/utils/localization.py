import os


UI_LANGUAGES = (
    ("system", "System Default"),
    ("en", "English"),
    ("it", "Italiano"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("hi", "हिन्दी"),
    ("pt", "Português"),
    ("es", "Español"),
    ("nb_NO", "Norsk bokmål"),
    ("pt_BR", "Português (Brasil)"),
    ("id", "Bahasa Indonesia"),
    ("da", "Dansk"),
    ("nl", "Nederlands"),
    ("tr", "Türkçe"),
    ("sv", "Svenska"),
    ("ru", "Русский"),
    ("eo", "Esperanto"),
    ("zh_Hans", "简体中文"),
    ("fi", "Suomi"),
    ("ja", "日本語"),
    ("hr", "Hrvatski"),
    ("cs", "Čeština"),
    ("uk", "Українська"),
    ("hu", "Magyar"),
    ("pl", "Polski"),
    ("zh_Hant", "繁體中文"),
    ("ko", "한국어"),
    ("vi", "Tiếng Việt"),
    ("eu", "Euskara"),
    ("bg", "Български"),
    ("el", "Ελληνικά"),
    ("gl", "Galego"),
    ("sk", "Slovenčina"),
    ("ro", "Română"),
    ("ms", "Bahasa Melayu"),
    ("ckb", "کوردیی ناوەندی"),
    ("fa", "فارسی"),
    ("th", "ไทย"),
    ("ar", "العربية"),
    ("bn", "বাংলা"),
    ("sl", "Slovenščina"),
    ("ca", "Català"),
    ("lt", "Lietuvių"),
    ("sr", "Српски"),
    ("et", "Eesti"),
    ("ta", "தமிழ்"),
    ("he", "עברית"),
    ("be", "Беларуская"),
    ("ie", "Interlingue"),
    ("az", "Azərbaycanca"),
    ("bs", "Bosanski"),
    ("kw", "Kernewek"),
    ("kab", "Taqbaylit"),
    ("ka", "ქართული"),
    ("yi", "ייִדיש"),
    ("oc", "Occitan"),
    ("lv", "Latviešu"),
)
UI_LANGUAGE_CODES = {code for code, _name in UI_LANGUAGES}
_INHERITED_LANGUAGE = os.environ.get("LANGUAGE")


def apply_ui_language(language):
    if language != "system" and language in UI_LANGUAGE_CODES:
        os.environ["LANGUAGE"] = language


def get_ui_language_environment(language):
    environment = os.environ.copy()
    environment.pop("GTK_THEME", None)

    if language == "system":
        if _INHERITED_LANGUAGE is None:
            environment.pop("LANGUAGE", None)
        else:
            environment["LANGUAGE"] = _INHERITED_LANGUAGE
    elif language in UI_LANGUAGE_CODES:
        environment["LANGUAGE"] = language

    return environment
