i18n = import('i18n')
fs = import('fs')

# Add legacy language code alias
# Fix missing locale for Chinese
# See also: https://docs.weblate.org/en/latest/faq.html#why-does-weblate-use-language-codes-such-sr-latn-or-zh-hant
language_list = fs.read('LINGUAS').strip().split('\n')
language_list += ['zh_CN', 'zh_HK', 'zh_SG', 'zh_TW']

i18n.gettext(
	'bottles',
	install_dir: localedir,
	preset: 'glib',
	args: '--from-code=UTF-8',
	languages: language_list
)
