import vyperlink
v=vyperlink.Vyperlink()

v.detect_interface()
v.identify_computer()

if v.model == vyperlink.VYPER:
	print "Okay, it's a vyper."

info = v.read_info()
print "personal: %s\nserial: %s\nsampling rate: %is\nmaxdepth: %.0f\ndives: %i"\
		% (info["personal"], info["serial"], info["sampling"],
				info["maxdepth"], info["numdives"])

lastdate = "2005-07-21T00:00"
# get first profile
prof = v.get_profile(start=True, last=lastdate)
print "got dive from %4d-%02d-%02d @%02d:%02d to %.0f meters" \
	% (prof['year'], prof['month'], prof['day'], 
	   prof['hr'], prof['min'], min(prof['profile']))

print "the samples were: ",
for depth in prof["profile"]:
	print depth,
print "\n"

print "getting dives up until %s" % lastdate
# if we got a profile, get the next up to last date
if prof:
	while True:
		prof = v.get_profile(start=False, last=lastdate)
		if prof == None:
			break
		print "got dive from %4d-%02d-%02d @%02d:%02d to %.0f meters" \
			% (prof['year'], prof['month'], prof['day'], 
			   prof['hr'], prof['min'], min(prof['profile']))


