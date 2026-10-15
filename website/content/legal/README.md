# Approved legal documents

Counsel's approved text for each legal page goes here as `<document>.md`, one of `privacy`, `terms`,
`cookies` and `subprocessors`. A page shows its draft notice until both conditions hold:

1. its decision in `config/decisions.json` is decided (LEG-01, LEG-02, LEG-03 or LEG-05), and
2. its approved text is here.

A build fails if a document is marked approved but its text is missing. A publish build fails while any
document is unapproved.
