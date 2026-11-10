-- Has Word update every field and list in the open report, saves it, and exports a PDF for checking.
on run argv
	set pdfPath to item 1 of argv
	with timeout of 600 seconds
		tell application "Microsoft Word"
			set d to active document
			repeat 2 times
				repeat with t in (get tables of contents of d)
					update t
				end repeat
				repeat with t in (get tables of figures of d)
					update t
				end repeat
				update fields (text object of d)
			end repeat
			save active document
			save as active document file name pdfPath file format format PDF
			return name of active document
		end tell
	end timeout
end run
