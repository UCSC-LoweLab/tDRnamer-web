#! /usr/bin/perl

use Cwd;
require "cgi-lib.pl";
require "tDRnamer-wwwlib.pl";

#*****************************************************************************************
#
# tDRList.cgi by Patricia Chan and Todd Lowe
#
# CGI script that displays tDR info for tDRnamer web server
#
#*******************************************************************************************


#Make output unbuffered.
$| = 1;

#Parent Process

if ($child = fork) {

    $SIG{'USR1'} = 'exit_parent';
    $SIG{'TERM'} = 'kill_child';

    while (1) {

	sleep(3);
#	print "<!-- Are you there? -->\n";

    }

    #Parent does nothing.
    #Forks and exits.
    #This way the web server won't kill the Search process after timeout.

}

#Child Process

elsif (defined $child) {

    $root = $ENV{'DOCUMENT_ROOT'};
	$configurations = &read_configuration_file();
    $TEMP = $configurations->{"temp_dir"};
    $EXEC = $configurations->{"bin_dir"};
    $LIB  = $configurations->{"lib_dir"};
	$DOWNLOAD_TEMP = $configurations->{"download_temp_dir"};
	$google_analytics = $configurations->{"google_analytics"};

    $SIG{'TERM'} = 'exit_signal';

    #File to log site information
    $LOG_FILE = "$TEMP/tDRnamer_list.log";

    #Queue Files for tDR cluster search
    $QUEUE_FILE = "$TEMP/tDRnamer_list_Queue";

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

    #Get Parameters
    &ReadParse;

	$RUN = $in{'run'};
    $ORG = $in{'org'};
	$SEARCHTYPE = $in{'searchType'};
	$PREFIX = substr($RUN, index($RUN, "_")+1);
	
	$DOWNLOAD_TEMP_RUN = $DOWNLOAD_TEMP."/run".$RUN;
    $SeqFile = $DOWNLOAD_TEMP_RUN."/seq$PREFIX";

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
    
    #If "USR1" signal is received, User has stopped the connection   
    #after timeout has occurred. Exit all scripts running on this search.
    $SIG{'USR1'} = 'exit_signal';

    #User has stopped the connection before timeout. Exit script.
    $SIG{'PIPE'} = 'exit_signal';

    #Insert Query in Queue
    &Insert_Queue;

    sleep(2);

    #Check if this query is next in the Queue
    #If not, Wait. 
    &Wait_Turn;

    #Get starting time.
    $start_time = time;

    #Get finishing time.
    $finish_time = time;

    #HTML Search Output 
    #Output to the browser (before timeout).

	# Print out the beginning of the HTML Page for the output
	&Start_HTML_Page;

	# Print out the results
	&PrintOut();

	# Print Out the End of the HTML Page
	&End_HTML_Page;

    # Remove Query from the Queue
    $RPID = $PID;
    &Remove_Queue;

    #Log Search Info.
    &Log_Info;

    if (getppid != 1) { kill ('USR1', getppid); }


} else {

    die "Can't Fork: $!\n";

}

exit 0;



#************************************
#
# *** END OF MAIN PROGRAM ***********
#
#************************************


sub Log_Info {

    
    if (!($ENV{'REMOTE_HOST'} =~ /wol|wyrm|woozle|wallaby/)) {
    
	$date = `date +'%m/%d/%y %H:%M'`;
	chop($date);
	$total_time = $finish_time - $start_time;

	open(LOG, ">>$LOG_FILE") || die "Can't open Log File: $LOG_FILE";

	flock(LOG, 2);

	print (LOG "$date tDRlist TIME: $total_time ",
	           "Length: $Length HOST: $ENV{'REMOTE_HOST'}\n");

	flock(LOG, 8);

	close(LOG);

    }

}


sub Start_HTML_Page {

    &HTMLHead("tDRnamer Results", $google_analytics);
}


sub CheckOutput
{
	my $valid = 1;
	
	if ($SEARCHTYPE eq "sequence")
	{
		if (-r "$SeqFile-tDR-list.txt" and -r "$SeqFile-tDR-groups.txt" and -r "$SeqFile-tDR-summary.json" and -r "$SeqFile-tDR-info.txt")
		{
			my ($line_count, $dummy) = split(/\s+/, `wc -l $SeqFile-tDR-list.txt`);
			if ($line_count <= 1)
			{
				$valid = 0;
			}
			($line_count, $dummy) = split(/\s+/, `wc -l $SeqFile-tDR-groups.txt`);
			if ($line_count < 1)
			{
				$valid = 0;
			}
			($line_count, $dummy) = split(/\s+/, `wc -l $SeqFile-tDR-summary.json`);
			if ($line_count <= 5)
			{
				$valid = 0;
			}
			($line_count, $dummy) = split(/\s+/, `wc -l $SeqFile-tDR-info.txt`);
			if ($line_count < 1)
			{
				$valid = 0;
			}
		}
		else
		{
			$valid = -1;
		}	
	}
	else
	{
		if (-r "$SeqFile-name-tDR-summary.json")
		{
			my ($line_count, $dummy) = split(/\s+/, `wc -l $SeqFile-name-tDR-summary.json`);
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

    print <<END_of_HTML;

<div class="row">
	<div class="small-12 medium-12 large-12 columns" style="overflow:auto">
<HR>
<h4><b>Results</b></h4>

END_of_HTML

	if ($valid == 0)
	{
		print "<BR><B>No tRNA-derived RNAs found</B><BR><BR>\n\n";
		return;
	}
	if ($valid == -1)
	{
		print "<BR><B>Query is in progress or waiting in a queue. Please check back later.</B><BR><BR>\n\n";
		return;
	}
	
	my $file_prefix = "seq".$PREFIX;
	
	my ($line_count, $dummy) = split(/\s+/, `wc -l $SeqFile-tDR-info.txt`);
	if ($line_count > 1)
	{		
		print "<div class=\"row\">\n";
		$FILE_LINK = "run".$RUN."/".$file_prefix."-tDR.fa";
		print "<div class=\"medium-3 columns\"><a href=\"/download/tDRnamer/".$FILE_LINK."\" download target=_blank>Download tDR sequences</a></div>\n";	
		$FILE_LINK = "run".$RUN."/".$file_prefix."-tDR-info.txt";
		print "<div class=\"medium-3 columns\"><a href=\"/download/tDRnamer/".$FILE_LINK."\" download target=_blank>Download tDR classifications</a></div>\n";	
		$FILE_LINK = "run".$RUN."/".$file_prefix."-tDR-groups.txt";
		print "<div class=\"medium-3 columns\"><a href=\"/download/tDRnamer/".$FILE_LINK."\" download target=_blank>Download tDR group info</a><br></div>\n";
		print "<div class=\"medium-3 columns\"></div></div>\n";
		print "\n\n<HR>\n";
	}
	print "<H5><b>tDR List</b></H5>\n";
	print "<P>To find out the details and grouping information, please click on the links in the table below for each corresponding tDR.</P>\n";
	
	if ($SEARCHTYPE eq "sequence")
	{
		$json_link = "\\/download\\/tDRnamer\\/"."run".$RUN."\\/".$file_prefix."-tDR-summary";
		my $cmd = "sed 's/\$json_link/".$json_link."/' ".$LIB."/tDRlist_html.txt | sed 's/\$org/".$ORG."/g' | sed 's/\$run/".$RUN."/g'";
		my $page = `$cmd`;
		print $page;
	}
	else
	{
		$json_link = "\\/download\\/tDRnamer\\/"."run".$RUN."\\/".$file_prefix."-name-tDR-summary";
		my $cmd = "sed 's/\$json_link/".$json_link."/' ".$LIB."/tDRnamelist_html.txt | sed 's/\$org/".$ORG."/g' | sed 's/\$run/".$RUN."/g'";
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
#    print "</body></html>\n";
    if ($NETSCAPE) { print "\n--NewData--\n"; }
}

# Report CGI Errors specified in variable $ERROR

sub CGI_Error {

    $Title = "CGI Error";
    &HTML_Header;

    print "$ERROR",
    "</BODY>\n",
    "</HTML>\n";

#    if ($NETSCAPE == 1) { print "\n--NewData--\n"; }

    &exit_signal;

}

# Sorting Algorithm (Sort by Seqf Coords)

sub HTML_Header {

    print "Content-type: text/html", "\n\n";


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
#    flock (QUEUE, 2);
    print (QUEUE "W $PID $est_time\n");
#    flock (QUEUE, 8);
    close (QUEUE);
}


sub Wait_Turn {

    #Has Queue Position changed ?
    $Old_Queue = -1;

    while (1) {

	if (-e $QUEUE_FILE) {

	    open(QUEUE, "+<$QUEUE_FILE");

	    flock(QUEUE, 2);

	    &Is_Process_Alive;

	    seek (QUEUE, 0, 0);
	    @NEXT = <QUEUE>;

	    if ($#NEXT > $MAX_QUEUE_SIZE) {

		$ERROR = "<H4>The server is too busy.<P> Try Again later.<P></H4>";

		&CGI_Error;

	    }

	    elsif (!@NEXT) {

		last;
		
	    }

	    @NEXT[0] =~ /^\S+\s+(\d+)/;

	    if ($1 == $PID) {
		@NEXT[0] =~ s/W/R/g;
		truncate (QUEUE, 0);
		seek (QUEUE, 0, 0);
		foreach $line (@NEXT) {
		    if ($line =~ s/\n//g) { 
			print (QUEUE "$line\n");
		    }
		}

		last;
	    }

	    $cum_time = 0;
	    for ($i = 0; $i <= $#NEXT; $i++) {
		@NEXT[$i] =~ /^\S+\s+(\d+)\s(\d+)/;
		$cum_time += $2;
		if ($1 == $PID) { 
		    last; 
		}
	    }

	    $In_Queue = $i;

	    if (($Old_Queue != $In_Queue) && ($METHOD ne 'mail')) {
		&Wait_Notice;
		$Old_Queue = $In_Queue;
	    }
	}

	else { last; }

	if ($METHOD ne 'mail') { 
#	    print "<!-- Are you there? -->\n"; 
	}


	flock(QUEUE, 8);	
	sleep(3);
    }

    flock(QUEUE, 8);
    close(QUEUE);
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

    $Title = "tDRList Queue";
    &HTML_Header;

    print "<CENTER>\n",
    "<P><BR>\n", "<H4>Your Query is waiting to be processed.<P>\n",
    "Please Wait...</H4><P><BR>", "There ";

    if ($In_Queue > 1) { print "are <B>$In_Queue</B> Queries "; }
    else { print "is <B>$In_Queue</B> Query</B> "; }

    print "to be processed before yours.<P><BR><BR>\n";
    print "Estimated time to finish queries ahead in the queue<BR>\n";
    printf ("<B>plus</B> your search is %.1f minutes<BR><BR>",
	    $cum_time/60);

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
		print (LOG "$date tDRdetails stopped TIME: $total_time ",
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

