-- Fills in the contents pages and saves. Argument: the .docx path.
on run argv
	set docPath to item 1 of argv
	set theFile to (POSIX file docPath) as alias
	tell application "Microsoft Word"
		activate
		open theFile
		delay 6
		set theDoc to active document
		update every table of contents of theDoc
		update every table of figures of theDoc
		update every table of contents of theDoc
		update every table of figures of theDoc
		save theDoc
		quit saving no
	end tell
end run
