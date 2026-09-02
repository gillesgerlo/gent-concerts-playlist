WINDOW_DAYS = 91

# Independent of WINDOW_DAYS above (which sizes the display/filter
# window). Two dates sharing (month, day) but differing in year are
# always >= ~365 calendar days apart, so vndg_crosscheck.find_year_correction
# can only ever find a match if the vndg fetch window is wide enough to
# span both the (possibly wrong) scraped date and the correct one -- 91
# days can never reach that far. 400 comfortably covers a full year in
# either direction of "today".
VNDG_CROSSCHECK_WINDOW_DAYS = 400
