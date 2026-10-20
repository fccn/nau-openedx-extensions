"""
Use the canonical casing of course keys, i.e. the one stored in the course overview.

MySQL matches course keys case-insensitively but the platform does not, so a link with a differently
cased key (e.g. ``+iBPC+`` for ``+IBPC+``) breaks the pages that use the course block structure.
"""
