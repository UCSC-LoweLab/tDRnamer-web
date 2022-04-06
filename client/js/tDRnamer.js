// tDRnamer.js

function checkInput(form)
{
	// regular expression to match only alphanumeric characters, hyphen, underscore, and colon
	var reText = /^[\w\-\_\:]+$/;
	
	// regular expression to match only sequences in FASTA format
	var reFasta = /[\<\#\$\!\@\%\?]+/;
	
	// regular expression to match only sequences
	var reSeq = /^[ACGTUacgtu\n]+$/;

	// regular expression to match only tDR names
	var reName = /^[A-Za-z0-9-:\n]+$/;

	if(form.seqname.value != "" && !reText.test(form.seqname.value))
	{
		alert("Error: Sequence name can only contain alphanumeric and the following special characters "+'\n'+"- _ :");
		form.seqname.focus();
		return false;
	}
	
	if(form.qformat.value == "formatted" && (form.qseq.value != ""))
	{
		if (reFasta.test(form.qseq.value))
		{
			alert("Error: FASTA-formatted sequences cannot contain the following special characters < # $ ! @ % ?");
			form.qseq.focus();
			return false;
		}
	}
	
	if(form.qformat.value == "raw" && (form.qseq.value != "") && !reSeq.test(form.qseq.value))
	{
		alert("Error: Raw sequences should only contain A, C, G, T, or U");
		form.qseq.focus();
		return false;
	}

	if (form.qseq.value && form.seqfile.value)
	{ 
	   return confirm("\n" + 
		   "You are submitting pasted sequence and a file sequence.\n" +
	 	   "The server will only search the file submitted.\n\n" +
		   "If you want to search the pasted sequence \n" +
		   "press 'Cancel', clear the file name, and then submit again.\n"); 
	}

	if(form.qname.value != "" && !reName.test(form.qname.value))
	{
		alert("Error: tDR names can only contain alphanumeric and the following special characters - :");
		form.seqname.focus();
		return false;
	}

	if (form.qname.value && form.namefile.value)
	{ 
	   return confirm("\n" + 
		   "You are submitting pasted names and a file.\n" +
	 	   "The server will only search the file submitted.\n\n" +
		   "If you want to search the pasted names \n" +
		   "press 'Cancel', clear the file name, and then submit again.\n"); 
	}
	
	return true;
}

