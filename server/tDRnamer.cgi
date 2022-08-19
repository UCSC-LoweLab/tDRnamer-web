#! /usr/bin/perl

require "cgi-lib.pl";
require "tDRnamer-wwwlib.pl";


#*****************************************************************************************
#
# tDRnamer.cgi
#
# CGI script that runs tDRnamer program
# adapted from Pfam HMM CGI script
#
#*******************************************************************************************


#Make output unbuffered.
$| = 1;

#Parent Process

if ($child = fork) {

    $SIG{'USR1'} = 'exit_parent';
    $SIG{'TERM'} = 'kill_child';

    while (1) {

#	sleep(3);
	# replacement command for sleep() - no clue why sleep doesn't work ??
	select(undef,undef,undef,3.0);

	# Creates an error
#	print "<!-- Are you there? -->\n";

    }

    #Parent does nothing.
    #Forks and exits.
    #This way the web server won't kill the Search process after timeout.
    
}

#Child Process

elsif (defined $child) {
##if (1) {

    $root = $ENV{'DOCUMENT_ROOT'};
	$configurations = &read_configuration_file();
	$genome_info = undef;
    $TEMP = $configurations->{"temp_dir"};
    $EXEC = $configurations->{"bin_dir"};
    $LIB  = $configurations->{"lib_dir"};
	$DOWNLOAD_TEMP = $configurations->{"download_temp_dir"};
	$genome_file = $configurations->{"genome_file"};
	$host_url = $configurations->{"host_url"};
	$google_analytics = $configurations->{"google_analytics"};

	$Max_query_len = $configurations->{"max_query_len"};
	$Max_query_seq = $configurations->{"max_query_seq"};
	$Max_query_seq_max_mode = $configurations->{"max_query_seq_max_mode"};
	$Max_seq_display = $configurations->{"max_seq_display"};
	$Max_query_name = $configurations->{"max_query_name"};
	$Max_query_name_max_mode = $configurations->{"max_query_name_max_mode"};
	$Max_name_display = $configurations->{"max_name_display"};

    $SIG{'TERM'} = 'exit_signal';

    #File to log site information
    $LOG_FILE = "$TEMP/tDRnamer.log";

    #Multple Queue Files for tDR searches
    $QUEUE_FILE_PREFIX = "$TEMP/tDRnamer_Queue";
    $Max_Queues = $configurations->{"max_queues"};
    $found_empty_queue = 0;
    foreach $qnum (1..$Max_Queues) 
    {
		$QUEUE_FILE = $QUEUE_FILE_PREFIX.$qnum;
		if (!-e $QUEUE_FILE) {
			system("touch $QUEUE_FILE");
		}
		if (-z $QUEUE_FILE) {
			$found_empty_queue = 1;
			last;
		}
    }
    # If you didn't find an empty queue file, pick one at random
    if (!$found_empty_queue) {
		$qnum = int(rand($Max_Queues))+1;
		$QUEUE_FILE = $QUEUE_FILE_PREFIX.$qnum;
    }
    
    #Maximum number of searches in each queue
    $MAX_QUEUE_SIZE = $configurations->{"max_queue_size"};

    # For whatever reason, MS Internet Explorer 4.0 claims to be
    # Mozilla/4.0, so we can't simply use Mozilla to distinguish
    # a Netscape browser w/ server push capability
    #
    if ($ENV{'HTTP_USER_AGENT'} =~ /Mozilla/
	&& ! ($ENV{'HTTP_USER_AGENT'} =~ /MSIE/)) { $NETSCAPE = 1; }
    else { $NETSCAPE = 0; }

    if ($ENV{'HTTP_USER_AGENT'} =~ /Chrome/)   { $CHROME = 1; $NETSCAPE = 1; }

    #Process ID
    $PID = $$;
	$run_PID = time()."_".$PID;

    #Get Parameters
    &ReadParse;
	
	$SEARCHTYPE = $in{'searchType'};
	$SEARCHMODE = $in{'mode'};
    $FORMAT = $in{'qformat'};
    $ORG = $in{'organism'};
    $SEQ = $in{'qseq'};
    $REMOTEFILE = $in{'seqfile'};
    $SEQNAME = $in{'seqname'};
	$ADDRESS = $in{'address'};
	$TDRNAME = $in{'qname'};
    $NAMEFILE = $in{'namefile'};

	$send_results = 0;

    if ($CHROME)
	{
		print "Content-type: multipart/x-mixed-replace\n"; 
    }
    elsif ($NETSCAPE)
	{
		#Print out MIME TYPE
		print "Content-type: multipart/x-mixed-replace;boundary=NewData", 
		"\n\n","\n--NewData\n";
    }
    else
	{
	# Required to fix IE4 "server error" problem
	# Added 2/5/99 by TML

#	print "Content-type: text/html\n\n";
    }

    #Check for security
	($in_valid, $invalid_key, $invalid_value) = &check_input(\%in);
	if (!$in_valid)
	{
		$ERROR = "<H4>Invalid input values.\n".
					 "Please go Back and check your entries</H4><BR>\n".
			 "<FORM>".
			 "<INPUT TYPE=BUTTON VALUE=\"Click here to go back\" onClick=\"history.back()\">".
			 "</FORM>";
	
		$ERROR .= "<p>".$invalid_key."<br>".$invalid_value."</p>";
		
		&CGI_Error; 
	}
	
    &Security;
    
    #If "USR1" signal is received, User has stopped the connection   
    #after timeout has occurred. Exit all scripts running on this search.
    $SIG{'USR1'} = 'exit_signal';

    #User has stopped the connection before timeout. Exit script.
    $SIG{'PIPE'} = 'exit_signal';

	$DOWNLOAD_TEMP_RUN = $DOWNLOAD_TEMP."/run".$run_PID;
	$SeqFile = "";
	$NameFile = "";

	$genome_info = &Get_genome_info($genome_file, $ORG);

	if ($SEARCHTYPE eq "sequence")
	{
		#If there was no sequence submitted.
		if ((!$SEQ) && (!$REMOTEFILE))
		{ 
			$ERROR = "<H4>There was no sequence submited\n".
						 "Please go Back and reenter your sequence</H4><BR>\n".
				 "<FORM>".
				 "<INPUT TYPE=BUTTON VALUE=\"Click here to go back\" onClick=\"history.back()\">".
				 "</FORM>";
		
			&CGI_Error; 
		}
	
		if ($REMOTEFILE) { $SEQ = $REMOTEFILE; }
	
		$Length = length($SEQ);

		system("mkdir -p ".$DOWNLOAD_TEMP_RUN);
	
		#Save Query Sequence in temporary file.
		$SeqFile = $DOWNLOAD_TEMP_RUN."/seq$PID".".fa";
	
		if (!open(SEQFILE, ">$SeqFile"))
		{
			$ERROR = "<BR>Unable to open $SeqFile\nPlease report this problem to web adminstrator\n<BR>";
			&CGI_Error;
		}
		print SEQFILE "$SEQ\n";	
		close (SEQFILE);
		
		if ($FORMAT eq "raw")
		{
			if (!$SEQNAME) { $SEQNAME="Your-seq"; }	
			$SEQ = `$EXEC/raw2fasta '$SEQNAME' $SeqFile`;
		}     
		else
		{
			$SEQ = `$EXEC/reformat -d -u fasta $SeqFile`;
			if ($?) 
			{			
				if ($SeqFile =~/format of file/)
				{
					$SeqFile = "FATAL: Cannnot determine sequence format";
				}
				
				$ERROR = "<P>$SeqFile</P>".
				"<H5>Please reformat sequence correctly and submit again.</H5>".
				"If you continue to have problems try raw or FASTA format.<BR><BR>".
				"If that doesn't work, please e-mail Todd Lowe at".
				" <A HREF=\"mailto:lowe\@soe.ucsc.edu\">lowe\@soe.ucsc.edu</A> ".
				"with a copy of the error message above and the sequence being submitted. ($?, $PID)";
				
				&CGI_Error;
			}
		}
		
		# Write reformatted sequence back to temp file
		
		open (SEQFILE, ">$SeqFile");
		print (SEQFILE "$SEQ\n");
		close (SEQFILE);
	
		$Check_log = $DOWNLOAD_TEMP_RUN."/check_fasta.log";
		$Command = "$EXEC/tDRnamer/check_input_tdr --fasta ".$SeqFile." > ".$Check_log;
		system($Command);
	
		if ($?)
		{
			$ERROR = "Problem occurs when checking query sequences<BR><BR>".
				"Seq=".$SeqFile;
			&CGI_Error;
		}
		
		@lines = split(/\n/, `tail -n 6 $Check_log`);
		$ERROR = "";
		for (my $i = 0; $i < scalar(@lines); $i++)
		{
			my ($tag, $value) = split(/: /, $lines[$i]);
			if ($i == 0)
			{
				$query_length = $value;
			}
			
			if ($i == 0 and $SEARCHMODE eq "Max" and $value > $Max_query_seq_max_mode)
			{
				$ERROR = "<BR>The total number of sequences is over the maximum to be queried by our web server.<BR>".
					"Please limit the number of sequences to a maximum of ".$Max_query_seq_max_mode." when using maximum sensutuvuty search mode or consider using the command-line version of tDRnamer.<BR>";
			}
			elsif ($i == 0 and $SEARCHMODE ne "Max" and $value > $Max_query_seq)
			{
				$ERROR = "<BR>The total number of sequences is over the maximum to be queried by our web server.<BR>".
					"Please limit the number of sequences to a maximum of ".$Max_query_seq." or consider using the command-line version of tDRnamer.<BR>";
			}
			elsif ($i == 0 and $value > $Max_seq_display and (!defined $ADDRESS or $ADDRESS eq ""))
			{
				$ERROR = "<BR>There are ".$value." query sequences that may take longer processing time. ".
					"Please provide your email address to obtain the results upon completion.<BR>";
			}
			if ($i == 0 and $value > $Max_seq_display)
			{
				$send_results = 1;
			}
			elsif ($i == 1 and $value > 0)
			{
				$ERROR = "<BR>".$value." query sequences do not have sequence name. Please make adjustment accordingly.<BR>";
			}
			elsif ($i == 2 and $value > 0)
			{
				$ERROR = "<BR>".$value." query sequences have invalid character(s) in sequence name. Only alphanumeric, hyphen, underscore, and colon are allowed. Please make adjustment accordingly.<BR>";
			}
			elsif ($i == 3 and $value > 0)
			{
				$ERROR = "<BR>".$value." query sequences are below minimum length (15 nt). Please make adjustment accordingly.<BR>";
			}
			elsif ($i == 4 and $value > 0)
			{
				$ERROR = "<BR>".$value." query sequences are above maximum length (70 nt). Please make adjustment accordingly.<BR>";
			}		
			elsif ($i == 5 and $value > 0)
			{
				$ERROR = "<BR>".$value." query sequences contain invalid character(s). Only A, C, G, T, and U are accepted. Please make adjustment accordingly.<BR>";
			}		
		}
		if ($ERROR)
		{
			$ERROR .=  "<BR><BR><FORM>".
				 "<INPUT TYPE=BUTTON VALUE=\"Click here to go back\" onClick=\"history.back()\">".
				 "</FORM>";
			&CGI_Error;
		}
	}
	elsif ($SEARCHTYPE eq "name")
	{
		#If there was no name submitted.
		if ((!$TDRNAME) && (!$NAMEFILE))
		{ 
			$ERROR = "<H4>There was no tDR name submitted\n".
						 "Please go Back and reenter your sequence name</H4><BR>\n".
				 "<FORM>".
				 "<INPUT TYPE=BUTTON VALUE=\"Click here to go back\" onClick=\"history.back()\">".
				 "</FORM>";
		
			&CGI_Error; 
		}
	
		if ($NAMEFILE) { $TDRNAME = $NAMEFILE; }

		system("mkdir -p ".$DOWNLOAD_TEMP_RUN);
	
		#Save Query names in temporary file.
		$NameFile = $DOWNLOAD_TEMP_RUN."/seq$PID".".txt";
	
		if (!open(TDRNAMEFILE, ">$NameFile"))
		{
			$ERROR = "<BR>Unable to open $NameFile\nPlease report this problem to web adminstrator\n<BR>";
			&CGI_Error;
		}
		$TDRNAME =~ s/\r//g;
		print TDRNAMEFILE "$TDRNAME\n";	
		close (TDRNAMEFILE);

		$Check_log = $DOWNLOAD_TEMP_RUN."/check_name.log";
		if (lc($genome_info->{org_domain}) eq "eukaryota")
		{
			$Command = "$EXEC/tDRnamer/check_input_tdr_name --name ".$NameFile." --precursor > ".$Check_log;
		}
		else
		{
			$Command = "$EXEC/tDRnamer/check_input_tdr_name --name ".$NameFile." > ".$Check_log;
		}
		system($Command);
	
		if ($?)
		{
			$ERROR = "Problem occurs when checking query tDR names<BR><BR>".
				"tDR name=".$NameFile;
			&CGI_Error;
		}

		@lines = split(/\n/, `tail -n 3 $Check_log`);
		$ERROR = "";
		for (my $i = 0; $i < scalar(@lines); $i++)
		{
			my ($tag, $value) = split(/: /, $lines[$i]);
			if ($i == 0)
			{
				$query_length = $value;
			}
			
			if ($i == 0 and $SEARCHMODE eq "Max" and $value > $Max_query_name_max_mode)
			{
				$ERROR = "<BR>The total number of tDR names is over the maximum to be queried by our web server.<BR>".
					"Please limit the number of query names to a maximum of ".$Max_query_name_max_mode." with maximum sensitivity search mode or consider using the command-line version of tDRnamer.<BR>";
			}
			elsif ($i == 0 and $SEARCHMODE ne "Max" and $value > $Max_query_name)
			{
				$ERROR = "<BR>The total number of tDR names is over the maximum to be queried by our web server.<BR>".
					"Please limit the number of query names to a maximum of ".$Max_query_name." or consider using the command-line version of tDRnamer.<BR>";
			}
			elsif ($i == 0 and $value > $Max_name_display and (!defined $ADDRESS or $ADDRESS eq ""))
			{
				$ERROR = "<BR>There are ".$value." tDR names that may take longer processing time. ".
					"Please provide your email address to obtain the results upon completion.<BR>";
			}
			if ($i == 0 and $value > $Max_name_display)
			{
				$send_results = 1;
			}
			elsif ($i == 1 and $value > 0)
			{
				$ERROR = "<BR>".$value." query tDR names have invalid character(s). Please check the naming nomenclature on the Help page and make adjustment accordingly.<BR>";
			}
			elsif ($i == 2 and $value > 0)
			{
				$ERROR = "<BR>".$value." query tDR names have invalid format. Please check the naming nomenclature on the Help page and make adjustment accordingly.<BR>";
			}
		}
		if ($ERROR)
		{
			$ERROR .=  "<BR><BR><FORM>".
				 "<INPUT TYPE=BUTTON VALUE=\"Click here to go back\" onClick=\"history.back()\">".
				 "</FORM>";
			&CGI_Error;
		}
	}
	
    #Message for e-mail request
	if ($send_results)
	{
		if (getppid != 1) { kill ('USR1', getppid); }
		&Email_Message;	
	}

	$est_time = $query_length*2;

    #Insert Query in Queue
    &Insert_Queue;

    sleep(2);

    #Check if this query is next in the Queue
    #If not, Wait. 
    &Wait_Turn;
    
    # Tell the user to wait. We use Netscape server push here;
    # Internet Explorer users suffer.
    if (!$send_results && $NETSCAPE)
	{
		&HTML_Message($est_time);
	}

    #Get starting time.
    $start_time = time;

    #Classify tDRs
    &Run;
	
    #Get finishing time.
    $finish_time = time;

    #HTML Output 
    #Output to the browser (before timeout).

    if (!$send_results)
	{
        # Print out the beginning of the HTML Page for the output
		if (!$NETSCAPE)
		{
			&HTMLHead("tDRnamer Results", $google_analytics);
		}

        # Print out the results
		&PrintOut;

        # Print Out the End of the HTML Page
		&End_HTML_Page;
    }
    #Send results via e-mail.
    else
	{
		&Email_Results;
    }

    # Remove Query from the Queue
    $RPID = $PID;
    &Remove_Queue;

    #Log Search Info.
    &Log_Info;

    if (getppid != 1) { kill ('USR1', getppid); }
}
else
{
    die "Can't Fork: $!\n";
}

exit 0;



#************************************
#
# *** END OF MAIN PROGRAM ***********
#
#************************************

sub Email_Results {

    open (SENDMAIL, "| /usr/sbin/sendmail -t") || 
	die "Can't e-mail results to $ADDRESS";

    print (SENDMAIL "To: $ADDRESS\n", "From: tDRnamer <trna\@soe.ucsc.edu>\n", "Subject: tRNA-derived RNA naming results\n\n");
 
    print (SENDMAIL 
		"tDRnamer - tRNA-derived RNA naming server\n",
		"If you have any questions, please contact us at trna\@soe.ucsc.edu.\n",
		"------------------------------------------------------------------------------\n\n");

	my $valid = &CheckOutput();
	if (!$valid)
	{
		print (SENDMAIL "No tRNA-derived RNAs found\n\n\n");
	}
	else
	{
		print (SENDMAIL "Results can be retrieved using the following web link.\nThe link will be active for three weeks. If you would like to store the results, please download them in text file format available on the web page\n\n");
		my $url = $host_url."/cgi-bin/tDRList.cgi?run=".$run_PID."&org=".$ORG."&searchType=".$SEARCHTYPE;
		print (SENDMAIL $url."\n");			
	}
    close SENDMAIL;
}


sub Log_Info {

    
    if (!($ENV{'REMOTE_HOST'} =~ /aero/)) {
    
	$date = `date +'%m/%d/%y %H:%M'`;
	chop($date);
	$total_time = $finish_time - $start_time;

	open(LOG, ">>$LOG_FILE") || die "Can't open Log File: $LOG_FILE";

	flock(LOG, 2);

	print (LOG "$date tDRnamer TIME: $total_time ",
	           "Length: $Length HOST: $ENV{'REMOTE_HOST'}\n");

	flock(LOG, 8);

	close(LOG);

    }

}


sub HTML_Message {

#    local($est_time) = @_;

    &HTMLHead("tDRnamer Results", $google_analytics);
	
    print "<CENTER>\n",
		"<H5>tDR searching in progress. Please Wait ...</h5>\n";		
#	print "<img src=\"/tDRnamer/image/trna-spin-white-bg.gif\" /><br>\n";	
	print "(Total number of inputs = $query_length)\n<BR>";
#    if ($est_time < 60)
#	{ 
#		printf  ("Estimated search time is %.0f seconds\n",$est_time);
#    }
#    else
#	{
#		printf  ("Estimated search time is %.1f minutes\n",$est_time/60);
#    }

#    if (!$slow_search)
#	{
#		print "<BR><BR>(plus 5 second for each tRNA you expect to find)\n";
#    }

#    if (($est_time > 300) && $slow_search)
#	if ($MODE =~ /^NoHMM/)
#	{
#		print"<BR><BR>Please note that no hmm-filter searches",
#		" are very slow.<BR>Accordingly, please limit the size of",
#		" sequences submitted using these search modes, <BR>or download the",
#		" UNIX source and run the program locally...";
#    }
    
    print "</CENTER>\n";
    print "</BODY>\n",
    "</HTML>\n";
    
}


sub Email_Message {

	&HTMLHead("tDRnamer Results Link", $google_analytics);
	
	my $url = $host_url."/cgi-bin/tDRList.cgi?run=".$run_PID."&org=".$ORG."&searchType=".$SEARCHTYPE;
	
    print "<CENTER>\n", 
    "<H4>tDRnamer results will be available at the following link:</H4><br>",
	"<a href=\"".$url."\" target=_blank>".$url."</a><br>\n";
	if ($ADDRESS ne "")
	{
		print "<br>";
		print "<P>An email will be sent to the following address when the results are available:<br>",
		"$ADDRESS</P>\n";
	}
	
    print "<P><BR>\n", 
    "<HR SIZE=5 NOSHADE>\n",
    "<P><BR>\n", 
    "<A HREF=\"/tDRnamer/\">Back to tDRnamer Query Page</A>\n",
    "<P>\n", 
    "</CENTER>\n";
    print "</BODY>\n", 
    "</HTML>\n";
}


sub Run {

	if ($SEARCHTYPE eq "sequence")
	{
		&SequenceSearch();
	}
	elsif ($SEARCHTYPE eq "name")
	{
		&NameSearch();
	}
}

sub SequenceSearch
{
	$Command = "$EXEC/tDRnamer/tDRnamer -s ";
	$Command = $Command." ".$SeqFile;
	$Command = $Command." -o ".$DOWNLOAD_TEMP_RUN."/seq".$PID;
	$Command = $Command." -d ".$LIB."/".$ORG."/".$ORG;
	if (lc($genome_info->{org_domain}) eq "eukaryota")
	{
		$Command = $Command." -r euk";
	}
	elsif (lc($genome_info->{org_domain}) eq "bacteria")
	{
		$Command = $Command." -r bact";
	}
	elsif (lc($genome_info->{org_domain}) eq "archaea")
	{
		$Command = $Command." -r arch";
	}
	if ($SEARCHMODE eq "Max")
	{
		$Command = $Command." --max";
	}
	$Command = $Command." --skipcheck";
	$Command = $Command." --bin ".$EXEC;
	system($Command);
}

sub NameSearch
{
	$Command = "$EXEC/tDRnamer/tDRnamer -m name -n ";
	$Command = $Command." ".$NameFile;
	$Command = $Command." -o ".$DOWNLOAD_TEMP_RUN."/seq".$PID;
	$Command = $Command." -d ".$LIB."/".$ORG."/".$ORG;
	$Command = $Command." --genomes ".$genome_file;	
	if (lc($genome_info->{org_domain}) eq "eukaryota")
	{
		$Command = $Command." -r euk";
	}
	elsif (lc($genome_info->{org_domain}) eq "bacteria")
	{
		$Command = $Command." -r bact";
	}
	elsif (lc($genome_info->{org_domain}) eq "archaea")
	{
		$Command = $Command." -r arch";
	}
	if ($SEARCHMODE eq "Max")
	{
		$Command = $Command." --max";
	}
	$Command = $Command." --skipcheck";
	$Command = $Command." --bin ".$EXEC;
	system($Command);
}

sub Start_HTML_Page {

    &HTMLHead("tDRnamer Results", $google_analytics);
}

sub CheckOutput
{
	my $valid = 1;
	
	my $output_prefix = $DOWNLOAD_TEMP_RUN."/seq".$PID;

	if ($SEARCHTYPE eq "sequence")
	{
		if (-r $output_prefix."-tDR-list.txt" and -r $output_prefix."-tDR-groups.txt" and -r $output_prefix."-tDR-summary.json" and -r $output_prefix."-tDR-info.txt")
		{
			my ($line_count, $dummy) = split(/\s+/, `wc -l $output_prefix-tDR-list.txt`);
			if ($line_count <= 1)
			{
				$valid = 0;
			}
			($line_count, $dummy) = split(/\s+/, `wc -l $output_prefix-tDR-groups.txt`);
			if ($line_count < 1)
			{
				$valid = 0;
			}
			($line_count, $dummy) = split(/\s+/, `wc -l $output_prefix-tDR-summary.json`);
			if ($line_count <= 5)
			{
				$valid = 0;
			}
			($line_count, $dummy) = split(/\s+/, `wc -l $output_prefix-tDR-info.txt`);
			if ($line_count <= 1)
			{
				$valid = 0;
			}
		}
		else
		{
			$valid = 0;
		}
	}
	else
	{
		if (-r $output_prefix."-name-tDR-summary.json")
		{
			my ($line_count, $dummy) = split(/\s+/, `wc -l $output_prefix-name-tDR-summary.json`);
			if ($line_count <= 5)
			{
				$valid = 0;
			}
		}
		else
		{
			$valid = 0;
		}
	}
	
	return $valid;
}


sub PrintOut
{
	my $valid = &CheckOutput();
	
    print "<CENTER>\n","<h4>Search Completed</H4>\n","</CENTER>\n";

    print <<END_of_HTML;

<div class="row">
	<div class="small-12 medium-12 large-12 columns" style="overflow:auto">
<HR>
<h4><b>Results</b></h4>

END_of_HTML

	if (!$valid)
	{
#		print "<p>$Command</p>\n";
		print "<BR><B>No tRNA-derived RNAs found</B><BR><BR>\n\n";
		&HTMLFoot;
		return;
	}

	my $output_prefix = $DOWNLOAD_TEMP_RUN."/seq".$PID;
	my $file_prefix = "seq".$PID;
	
	my ($line_count, $dummy) = split(/\s+/, `wc -l $output_prefix-tDR-info.txt`);
	if ($line_count > 1)
	{		
		print "<div class=\"row\">\n";
		$FILE_LINK = "run".$run_PID."/".$file_prefix."-tDR.fa";
		print "<div class=\"medium-3 columns\"><a href=\"/download/tDRnamer/".$FILE_LINK."\" download target=_blank>Download tDR sequences</a></div>\n";			
		$FILE_LINK = "run".$run_PID."/".$file_prefix."-tDR-info.txt";
		print "<div class=\"medium-3 columns\"><a href=\"/download/tDRnamer/".$FILE_LINK."\" download target=_blank>Download tDR classifications</a></div>\n";	
		$FILE_LINK = "run".$run_PID."/".$file_prefix."-tDR-groups.txt";
		print "<div class=\"medium-3 columns\"><a href=\"/download/tDRnamer/".$FILE_LINK."\" download target=_blank>Download tDR group info</a><br></div>\n";	
		print "<div class=\"medium-3 columns\"></div></div>\n";
		print "\n\n<HR>\n";
	}
	print "<H5><b>tDR List</b></H5>\n";
	print "<P>To find out the details and grouping information, please click on the links in the table below for each correspoding tDR.</P>\n";
	
	if ($SEARCHTYPE eq "sequence")
	{
		$json_link = "\\/download\\/tDRnamer\\/"."run".$run_PID."\\/".$file_prefix."-tDR-summary";
		my $cmd = "sed 's/\$json_link/".$json_link."/' ".$LIB."/tDRlist_html.txt | sed 's/\$org/".$ORG."/g' | sed 's/\$run/".$run_PID."/g'";
	#	print "<P>$cmd</P>\n";
		my $page = `$cmd`;
		print $page;
	}
	else
	{
		$json_link = "\\/download\\/tDRnamer\\/"."run".$run_PID."\\/".$file_prefix."-name-tDR-summary";
		my $cmd = "sed 's/\$json_link/".$json_link."/' ".$LIB."/tDRnamelist_html.txt | sed 's/\$org/".$ORG."/g' | sed 's/\$run/".$run_PID."/g'";
	#	print "<P>$cmd</P>\n";
		my $page = `$cmd`;
		print $page;
	}

	print "\n";
}

sub trim
{
	my ($str) = @_;
	$str =~ s/^\s+|\s+$//g;
	return $str;
}

sub End_HTML_Page {
#    &HTMLFoot;
#    print "</body>\n</html>\n";
    if ($NETSCAPE) { print "\n--NewData--\n"; }
}

# Report CGI Errors specified in variable $ERROR

sub CGI_Error {

	&HTMLHead("tDRnamer Error", $google_analytics);

    print "<p>$ERROR</p>\n";
	
    print "</BODY>\n",
    "</HTML>\n";

#    if ($NETSCAPE == 1) { print "\n--NewData--\n"; }

    &exit_signal;

}


# Security check.
# Make sure the script gets what it expects.

sub Security {

    $ADDRESS =~ s/[^a-z0-9\.\@\_\-]/ /g;
    $ADDRESS =~ m|^(\S+).?|;
    $ADDRESS = $1;

}


# Sorting Algorithm (Sort by Seqf Coords)

sub HTML_Header {

#    print "Content-type: text/html", "\n\n";


    print "<HTML>\n",
    "<HEAD>\n",
    "<TITLE>\n",
    "$Title\n",
    "</TITLE>\n",
    "</HEAD>\n",
    "<BODY BGCOLOR=FFFFEE>\n";

}

# Queing Mechanism Subs follow

sub Insert_Queue {
    
    open (QUEUE, ">>$QUEUE_FILE");
    flock (QUEUE, 2);
#    print (QUEUE "W $PID Len=$query_length Est-time=$est_time\n");
    print (QUEUE "W $PID $est_time\n");
    flock (QUEUE, 8);
    close (QUEUE);
}


sub Wait_Turn
{
    #Has Queue Position changed ?
    $Old_Queue = -1;

    while (1)
	{
		if (-e $QUEUE_FILE)
		{	
			open(QUEUE, "+<$QUEUE_FILE");		
			flock(QUEUE, 2);
			
			&Is_Process_Alive;
			
			seek (QUEUE, 0, 0);
			@NEXT = <QUEUE>;
		
			if ($#NEXT > $MAX_QUEUE_SIZE)
			{
				$ERROR = "<H4>The server is too busy.<P> Try Again later.<P></H4>";
				&CGI_Error;
			}
			elsif (!@NEXT)
			{
				last;
			}
	
			@NEXT[0] =~ /^\S+\s+(\d+)/;
			if ($1 == $PID)
			{
				@NEXT[0] =~ s/W/R/g;
				truncate (QUEUE, 0);
				seek (QUEUE, 0, 0);
				foreach $line (@NEXT)
				{
					if ($line =~ s/\n//g)
					{ 
						print (QUEUE "$line\n");
					}
				}
	
				last;
			}
	
			$cum_time = 0;
			for ($i = 0; $i <= $#NEXT; $i++)
			{
				@NEXT[$i] =~ /^\S+\s+(\d+)\s(\d+)/;
				$cum_time += $2;
				if ($1 == $PID)
				{ 
					last; 
				}
			}
	
			$In_Queue = $i;
			
			if (($Old_Queue != $In_Queue) && ($ADDRESS eq ""))
			{
		#	    &Wait_Notice;
				$Old_Queue = $In_Queue;
			}
			
			else { last; }
		
			if ($ADDRESS eq "")
			{ 
		#	    print "<!-- Are you there? -->\n"; 
			}
			
			flock(QUEUE, 8);	
			select(undef,undef,undef,2.0);
		#	sleep(1);
		}
		
		flock(QUEUE, 8);
		close(QUEUE);
    }
}

sub Is_Process_Alive {

# Sun Solaris:
#    @ALIVE = `ps -e -o pid`;
# Linux:
    @ALIVE = `ps -axh | awk '{print $1}'`;

    seek(QUEUE, 0, 0);
    @NEXT = <QUEUE>;

    for ($l = 0; $l <= $#NEXT; $l++) {

	$Flag = 0;

	for ($p = 1; $p <= $#ALIVE; $p++) {
	    $NEXT[$l] =~ /^\S+\s+(\d+)/;
	    $query = $1;
	    $ALIVE[$p] =~ /(\d+)/;
	    if ($query == $1) { 
		$Flag = 1;
	    }
	}

	if ($Flag == 0) {

	    $RPID = $query;
	    &Remove_Queue;
	    if (-e $SeqFile) { system ("rm $SeqFile"); }
	}
    }
}


sub Remove_Queue {

    open (RMPID, "+<$QUEUE_FILE");
#    flock(RMPID, 2);
    @REMOVE = <RMPID>;

    foreach $pidn (@REMOVE) {
	$pidn =~ /^\S+\s+(\d+)/;
	if ($RPID == $1) {
	    $pidn = "";
	}
    }

    truncate (RMPID, 0);
    seek (RMPID, 0, 0);
    foreach $pidn (@REMOVE) {
	if ($pidn =~ s/\n//g) {
	    print (RMPID "$pidn\n");
	}
    }

#    flock(RMPID, 8);
    close (RMPID);
}


sub Wait_Notice {

    if ($METHOD eq 'mail') { return; }

    $Title = "tDRnamer Queue";
    &HTML_Header;

    print "<CENTER>\n",
    "<P><BR>\n", "<H4>Your Query is waiting to be processed.<P>\n",
    "Please Wait...</H4><P><BR>", "There ";

    if ($In_Queue > 1) { print "are <B>$In_Queue</B> Queries "; }
    else { print "is <B>$In_Queue</B> Query</B> "; }

    print "to be processed before yours.<P><BR><BR>\n";
    print "Estimated time to finish queries ahead in the queue<BR>\n";
    printf ("<B>plus</B> your search is %.1f minutes<BR><BR>",
	    $cum_time/10);

    print "If you prefer not to wait,<P>", 
    "go back to the previous screen and choose the results by e-mail option.<P>\n";

    print "</CENTER>\n", "</BODY>\n", "</HTML>\n";

    if ($NETSCAPE == 1) { print "\n--NewData\n"; }

}


# Termination Subroutines

sub exit_signal {

    $RPID = $PID;
    &Remove_Queue;
    $total_time = 0;

    if (-e "$SeqFile.pid")
	{
		open(PIDFILE, "$SeqFile.pid");
		$RPID = <PIDFILE>;
		close (PIDFILE);
	
		$RPID =~ /^PID=(\d+)$/;	
		$RPID = $1;	
		kill('TERM', $RPID);
    }

    if (!($ENV{'REMOTE_HOST'} =~ //))
	{
		$finish_time = time;
		$date = `date +'%m/%d/%y %H:%M`;
		chop($date);

		if ($start_time)
		{ 
			$total_time = $finish_time - $start_time;
		}

		open(LOG, ">>$LOG_FILE") || die "Can't open Log File: $LOG_FILE";
		flock(LOG, 2);
		print (LOG "$date tDRnamer stopped TIME: $total_time ",
				   "Length: $Length HOST: $ENV{'REMOTE_HOST'}\n");	
		flock(LOG, 8);	
		close(LOG);
    }

    if (getppid != 1)
	{
		kill('TERM', getppid);
    }

    exit(1);
}


sub exit_parent {

    exit(0);

}


sub kill_child {

    kill('USR1', $child);

    exit(1);

}

sub Error_Handler {


}

