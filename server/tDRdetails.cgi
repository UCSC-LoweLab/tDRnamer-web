#! /usr/bin/perl

use Cwd;
require "cgi-lib.pl";
require "tDRnamer-wwwlib.pl";

#*****************************************************************************************
#
# tDRdetails.cgi by Patricia Chan and Todd Lowe
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

	sleep(10);
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
	$genome_info = undef;
    $TEMP = $configurations->{"temp_dir"};
    $EXEC = $configurations->{"bin_dir"};
    $LIB  = $configurations->{"lib_dir"};
	$DOWNLOAD_TEMP = $configurations->{"download_temp_dir"};
	$genome_file = $configurations->{"genome_file"};
	$google_analytics = $configurations->{"google_analytics"};

    $SIG{'TERM'} = 'exit_signal';

    #File to log site information
    $LOG_FILE = "$TEMP/tDRnamer_details.log";

    #Queue Files for tDR details search
    $QUEUE_FILE = "$TEMP/tDRnamer_details_Queue";

    #Maximum number of searches in each queue
    $MAX_QUEUE_SIZE = $configurations->{"max_queue_size"};

    # For whatever reason, MS Internet Explorer 4.0 claims to be
    # Mozilla/4.0, so we can't simply use Mozilla to distinguish
    # a Netscape browser w/ server push capability
    #
    if ($ENV{'HTTP_USER_AGENT'} =~ /Mozilla/
	&& ! ($ENV{'HTTP_USER_AGENT'} =~ /MSIE/)) { $NETSCAPE = 1; }
    else { $NETSCAPE = 0; }

# New 6/22/2016  Never use Netscape settings for mozilla / chrome
    $NETSCAPE = 0;

    #Process ID
    $PID = $$;

    #Get Parameters
    &ReadParse;

	$RUN = $in{'run'};
    $ID  = $in{'id'};
    $ORG = $in{'org'};
	$PREFIX = substr($RUN, index($RUN, "_")+1);

    if ($NETSCAPE) {
	#Print out MIME TYPE
	print "Content-type: multipart/x-mixed-replace;boundary=NewData", 
	"\n\n","\n--NewData\n";
    }
    else {
	# Required to fix IE4 "server error" problem
	# Added 2/5/99 by TML

#	print "Content-type: text/html\n\n";
    }

    #Check for security
	($in_valid, $invalid_key, $invalid_value) = &check_input(\%in);
	if (!$in_valid)
	{
		$ERROR = "<H4>Invalid input values. ".
					 "Please contact administrator</H4><BR>\n".
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

	$genome_info = &Get_genome_info($genome_file, $ORG);
	
	my $tdr = &Get_tDR;
	&Get_full_name($tdr);
	my $alignments = &Get_alignments($tdr);
	if ($tdr->[1] eq "pre-tRNA")
	{
		$alignments = &Adjust_pre_tDR_alignments($alignments);
	}
	my $mfe_file = &Create_MFE_structure($tdr);
	my ($sequence, $structure, $mfe) = &Get_MFE_structure($mfe_file);
	&Create_MFE_image($sequence, $structure, $mfe_file);
	my $png_file = &Draw_tDR($alignments, $tdr);

    #Get finishing time.
    $finish_time = time;

    #HTML Search Output 
    #Output to the browser (before timeout).

	# Print out the beginning of the HTML Page for the output
	&Start_HTML_Page;

	# Print out the results
	&PrintResultHeader($tdr);
	&PrintDetails($tdr, $alignments, $mfe_file, $mfe, $sequence, $structure, $png_file);

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

	print (LOG "$date tDRdetails TIME: $total_time ",
	           "Length: $Length HOST: $ENV{'REMOTE_HOST'}\n");

	flock(LOG, 8);

	close(LOG);

    }

}

sub Get_tDR
{
	my $info_file = $DOWNLOAD_TEMP."/run".$RUN."/seq".$PREFIX."-tDR-info.txt";
	my $found = 0;
	my $line = "";
	my @tdr = ();
	open(FILE_IN, "$info_file") or die "Fail to open $info_file\n";
	while (($line = <FILE_IN>) and !$found)
	{
		chomp($line);
		@tdr = split(/\t/, $line);
		if ($tdr[0] eq $ID)
		{
			$found = 1;
		}
	}
	close(FILE_IN);

	return \@tdr;
}

sub Get_full_name
{
	my ($tdr) = @_;
	my $full_name = $tdr->[2];
	my $map_file = $DOWNLOAD_TEMP."/run".$RUN."/seq".$PREFIX."-tDR-fullname-map.txt";
	if (-r $map_file)
	{
		my $found = 0;
		my $line = "";
		my @rec = ();
		open(FILE_IN, "$map_file") or die "Fail to open $map_file\n";
		while (($line = <FILE_IN>) and !$found)
		{
			chomp($line);
			@rec = split(/\t/, $line);
			if ($rec[0] eq $ID)
			{
				$found = 1;
				$full_name = $rec[1];
			}
		}
		close(FILE_IN);

	}
	push(@$tdr, $full_name);
}

sub Get_alignments
{	
	my ($tdr) = @_;
	my @alignments = ();
	
	if (scalar(@$tdr) > 0)
	{
		my %seqs = ();
		my $cmd = "";
		my @lines = ();
		my @source_trnas = split(/\,/, $tdr->[4]);
		for (my $i = 0; $i < scalar(@source_trnas); $i++)
		{
			$seqs{$source_trnas[$i]} = $i;
		}
		$seqs{$ID} = scalar(@source_trnas);
		
		my $line = "";
		my $alignment_file = $DOWNLOAD_TEMP."/run".$RUN."/seq".$PREFIX."-tDRs.stk";
		if ($tdr->[1] eq "pre-tRNA")
		{
			$alignment_file = $DOWNLOAD_TEMP."/run".$RUN."/seq".$PREFIX."-pre-tDRs.stk";
		}
		
		open(FILE_IN, "$alignment_file") or die "Fail to open $alignment_file\n";
		while ($line = <FILE_IN>)
		{
			if (index($line, "#=GC SS_cons") == 0)
			{
				push(@lines, $line);
			}
			elsif ($line =~ /^#/) {}
			else
			{
				my ($seq_name, $align) = split(/\s+/, $line);
				if (defined $seqs{$seq_name})
				{
					$lines[$seqs{$seq_name}] = $line;
				}
			}
		}
		close(FILE_IN);
				
		if (scalar(@lines) == (scalar(keys %seqs) + 1))
		{
			@alignments = ("") x scalar(@lines); 
			my $skip = 1;
			my $start_pos = rindex($lines[0], " ") + 1;
			for (my $i = 0; $i < length($lines[0]); $i++)
			{
				$skip = 1;
				for (my $j = 0; $j < scalar(@lines); $j++)
				{
					if ($i < $start_pos)
					{
						if ($j == scalar(@lines) - 1)
						{
							$alignments[$j] .= " ";
						}
						else
						{
							$alignments[$j] .= substr($lines[$j], $i, 1);
						}
					}
					else
					{
						if ($j < (scalar(@lines) - 1))
						{
							if (substr($lines[$j], $i, 1) ne "." and substr($lines[$j], $i, 1) ne "-")
							{
								$skip = 0;
							}
						}
					}
				}
				if (!$skip)
				{
					for (my $j = 0; $j < scalar(@lines); $j++)
					{
						$alignments[$j] .= substr($lines[$j], $i, 1);
					}
				}				
			}			
		}
	}
	
	return \@alignments;
}

sub Adjust_pre_tDR_alignments
{
	my ($alignments) = @_;
	my @mod_alignments = ("") x scalar(@$alignments);
	my $left_start = 0;
	my $right_end = 0;
	my $align_len = 0;
	my $nt_ct = 0;
	my $tRNA_start = 0;
	my $tRNA_end = 0;
	
	my $start_pos = rindex($alignments->[0], " ") + 1;
	$left_start = $start_pos;
	$right_end = length($alignments->[0]) - 1;
	
	for (my $i = $start_pos; $i < length($alignments->[0]); $i++)
	{
		if (substr($alignments->[(scalar(@$alignments)-1)], $i, 1) eq "(")
		{
			if ($tRNA_start == 0)
			{
				$tRNA_start = $i;
			}
		}
		elsif (substr($alignments->[(scalar(@$alignments)-1)], $i, 1) eq ")")
		{
			$tRNA_end = $i + 1;
		}
		elsif (substr($alignments->[(scalar(@$alignments)-1)], $i, 1) eq ":")
		{
			if (substr($alignments->[(scalar(@$alignments)-2)], $i, 1) eq ".")
			{
				if ($align_len == 0)
				{
					$left_start = $i;
				}
				elsif ($nt_ct > 0 and $tRNA_start and ($i > $tRNA_end))
				{
					$right_end = $i;
					last;
				}
				else
				{
					$align_len++;
				}
			}
			else
			{
				$align_len++;
				$nt_ct++;
			}
		}
		else
		{
			$align_len++;
			if (substr($alignments->[(scalar(@$alignments)-2)], $i, 1) ne ".")
			{
				$nt_ct++;
			}			
		}
	}
	
	for (my $j = 0; $j < scalar(@$alignments); $j++)
	{
		$mod_alignments[$j] = substr($alignments->[$j], 0, $start_pos);
		$mod_alignments[$j] .= substr($alignments->[$j], $left_start+1, $right_end-$left_start-1);
		if ($right_end < length($alignments->[$j]) - 1)
		{
			$mod_alignments[$j] .= "\n";
		}		
	}
	
	return \@mod_alignments;
}

sub Create_MFE_structure
{
	my ($tdr) = @_;
	my $current_dir = getcwd;
	my $mod_tDR_name = $tdr->[0]."__".$tdr->[2];
	$mod_tDR_name =~ s/\:/\_/;
	$mod_tDR_name =~ s/\-/\_/g;
	my $mfe = "";
	my $out_file = $DOWNLOAD_TEMP."/run".$RUN."/".$mod_tDR_name."-MFE.txt";
	if (!-r $out_file)
	{
		my $result = chdir($DOWNLOAD_TEMP."/run".$RUN);
		if ($result == 1)
		{
			open (FILE_OUT, ">$mod_tDR_name") || die "Fail to open $mod_tDR_name\n";
			print FILE_OUT $tdr->[15];
			close (FILE_OUT);
			my $cmd = $EXEC."/RNAfold < ".$mod_tDR_name." > ".$mod_tDR_name."-MFE.txt";
			system($cmd);
			system("rm rna.ps");
			if (-r $mod_tDR_name."-MFE.txt")
			{
				$out_file = $mod_tDR_name."-MFE.txt";
			}
			chdir($current_dir);
		}
	}
	else
	{
		$out_file = $mod_tDR_name."-MFE.txt";
	}
	return $out_file;
}

sub Get_MFE_structure
{
	my ($mfe_file) = @_;
	my $line = "";
	my $seq = "";
	my $structure = "";
	my $mfe = "";

	my $filename = $DOWNLOAD_TEMP."/run".$RUN."/".$mfe_file;
	if (-r $DOWNLOAD_TEMP."/run".$RUN."/".$mfe_file)
	{
		open (FILE_IN, "$filename") || die "Fail to open $filename\n";
		$line = <FILE_IN>;
		chomp($line);
		$seq = $line;
		$line = <FILE_IN>;
		chomp($line);
		$structure = substr($line, 0, index($line, " "));
		if ($line =~ / \((.+)\)$/)
		{
			$mfe = $1;
		}
		close (FILE_IN);
	}

	return ($seq, $structure, $mfe);
}

sub Create_MFE_image
{
	my ($seq, $structure, $mfe_file) = @_;
	my $png_file = $DOWNLOAD_TEMP."/run".$RUN."/".substr($mfe_file, 0, length($mfe_file)-3)."png";
	my $eps_file = $DOWNLOAD_TEMP."/run".$RUN."/".substr($mfe_file, 0, length($mfe_file)-3)."eps";
	my $cmd = "java -cp $EXEC/VARNAv3-93.jar fr.orsay.lri.varna.applications.VARNAcmd -sequenceDBN ".$seq." -structureDBN \"".$structure."\" -algorithm naview -o ";
	if (!-r $png_file or !-r $eps_file)
	{
		system($cmd.$eps_file." > /dev/null 2>&1");
		system("convert -density 150 eps:$eps_file png:$png_file");
	}
}

sub Draw_tDR
{
	my ($alignments, $tdr) = @_;
	my $mod_tDR_name = $tdr->[0]."__".$tdr->[2];
	$mod_tDR_name =~ s/\:/\_/;
	$mod_tDR_name =~ s/\-/\_/g;
	my $png_file = $mod_tDR_name."-align.png";
	my $current_dir = getcwd;	

	chdir($DOWNLOAD_TEMP."/run".$RUN);

	if (!-r $png_file)
	{
		my $ss = $alignments->[scalar(@$alignments)-1];
		$ss = substr($ss, rindex($ss, " ")+1);
		$ss =~ s/</\(/g;
		$ss =~ s/>/\)/g;
		$ss =~ s/_/\./g;
		$ss =~ s/:/\./g;
		$ss =~ s/,/\./g;
		$ss =~ s/-/\./g;
		$ss =~ s/\(/\>/g;
		$ss =~ s/\)/\</g;
		my $seq = $alignments->[scalar(@$alignments)-2];
		$seq = substr($seq, rindex($seq, " ")+1);
		$seq =~ s/\./N/g;
		my $diff_pos = &find_diff_pos($tdr->[scalar(@$tdr)-1], $seq);

		my $cmd = "";
		my $ss_file = $mod_tDR_name."-align.ss";
		my $ct_file = $mod_tDR_name."-align.ct";
		my $plt2_file = $mod_tDR_name."-align.plt2";
		my $ps_file = $mod_tDR_name."-align.orig.ps";
		open(FILE_OUT, ">$ss_file");
		print FILE_OUT $tdr->[2]."\n";
		print FILE_OUT "Seq: ".$seq;
		print FILE_OUT "Str: ".$ss;
		close(FILE_OUT);

		$cmd = $EXEC."/tRNAss2ct < ".$ss_file." > ".$ct_file;
		system($cmd);
		$cmd = "cat ".$EXEC."/tRNA.nav | ".$EXEC."/naview ".$ct_file." ".$plt2_file." > /dev/null";
		system($cmd);
		$cmd = $EXEC."/plt2ps ".$plt2_file." ".$ps_file." > /dev/null";
		system($cmd);

		my $ps_mod_file = &hack_ps($ps_file, $tdr, $diff_pos);
		system("convert -density 150 ps:$ps_mod_file png:$png_file");
	}
	chdir($current_dir);

	return substr($png_file, rindex($png_file, "/")+1);
}

sub hack_ps 
{
	my ($ps_file, $tdr, $diff_pos) = @_;
	my $mod_tDR_name = 	$tdr->[2];
	$mod_tDR_name =~ s/\:/\_/;
	$mod_tDR_name =~ s/\-/\_/g;
	my $ps_mod_file = $mod_tDR_name."-align.ps";
    my $start_bases = 0;
	my $start_tdr = 0;
	my $count = 0;

	open(PSF,"$ps_file");
    open(NEWPSF,">$ps_mod_file");

    while ($line = <PSF>) 
	{
		if ($line =~ /^\/dot/)
		{
			$line =~ s/\.2  0.0  360.0  arc  fill/\.1  0.0  360.0  arc  fill/;
		}
		elsif (index($line, $tdr->[2]) > -1)
		{
			$line =~ s/show//;
		}
		elsif ($line =~ /^\/yshift/) 
		{
			if ($tdr->[1] eq "pre-tRNA")
			{
				$line = "/yshift 10.00 def\n";
			}
			else
			{
				$line = "/yshift 12.00 def\n";
			}
		}
		elsif ($line =~ /^0 0 0 setrgbcolor/)
		{
			$line = ".5 .5 .5 setrgbcolor\n";
		}
		elsif ($line =~ /^\.85 \.15 \.25 setrgbcolor/)
		{
			$line = ".5 .5 .5 setrgbcolor\n";
		}
		elsif ($line =~ /^\.25 \.20 \.65 setrgbcolor/)
		{
			$line = ".5 .5 .5 setrgbcolor\n";
		}
		elsif ($line =~ /^\/sz/) 
		{
			$line = "/sz 36.00 scf div 0.5 mul def\n";
		}
		elsif ($line =~ /^\/Helvetica/)
		{
			$line =~ s/Helvetica/Helvetica-Bold/;
		}
		elsif ($line eq "% CM BASES\n")
		{
			$start_bases = 1;
		}
		elsif ($line eq "% CM BASE PAIRS\n")
		{
			$start_bases = 0;
		}
		else
		{
			if ($start_bases and $line =~ /show/ and $line !~ /\(I\) show/ and $line !~ /\(X\) show/)
			{
				if (defined $diff_pos->{$count})
				{
					$line = ".85 .15 .25 setrgbcolor\n".$line.".15 .5 .20 setrgbcolor\n";
				}
				$count++;
			}
			$line =~ s/\(N\) show/\(-\) show/;
			$line =~ s/\(X\) show/\(\) show/;
			$line =~ s/\(I\) show/\(Intron\) show/;
			if (($start_tdr == 0) and ($line =~ /\(A\) show/ or $line =~ /\(C\) show/ or $line =~ /\(G\) show/ or $line =~ /\(U\) show/))
			{
				$start_tdr = 1;
				$line = ".15 .5 .20 setrgbcolor\n".$line;
			}
			if ($start_tdr and $line =~ /\(-\) show/)
			{
				$start_tdr = 0;
				$line = ".5 .5 .5 setrgbcolor\n".$line;
			}
		}
		
		print NEWPSF $line;
    }
    close PSF;
    close NEWPSF;

	return $ps_mod_file;
}

sub Start_HTML_Page 
{
    &HTMLHead("tDR Details", $google_analytics);
}

sub GetAlignmentLocation
{
	my ($position, $source) = @_;
	my $location = "";
	
	my ($start, $end) = split(/\.\./, $position);
	$location = &decode_position($start)." to ".&decode_position($end);
	
	if ($location eq "" and $source eq "pre-tRNA")
	{
		$location = "Pre-tRNA";
	}
	
	return $location;
}

sub decode_position
{
	my ($pos) = @_;
	my $location = "";
	
	if (substr($pos, 0, 1) eq "-")
	{
		$location = "5' leader";
	}
	elsif (substr($pos, 0, 1) eq "+")
	{
		$location = "3' trailer";
	}
	elsif (substr($pos, 0, 1) eq "e")
	{
		$location = "Variable loop";
	}
	elsif (lc($pos) eq "17a" or lc($pos) eq "20a" or lc($pos) eq "20b")
	{
		$location = "D loop";
	}
	else
	{
		my $num_pos = int($pos);
		if ($num_pos >= 1 and $num_pos <= 7)
		{
			$location = "Acceptor stem";
		}
		elsif ($num_pos >= 8 and $num_pos <= 9)
		{
			$location = "Between acceptor stem and D arm";
		}
		elsif ($num_pos >= 10 and $num_pos <= 13)
		{
			$location = "D arm";
		}
		elsif ($num_pos >= 14 and $num_pos <= 21)
		{
			$location = "D loop";
		}
		elsif ($num_pos >= 22 and $num_pos <= 25)
		{
			$location = "D arm";
		}
		elsif ($num_pos == 26)
		{
			$location = "Between D arm and anticodon stem";
		}
		elsif ($num_pos >= 27 and $num_pos <= 31)
		{
			$location = "Anticodon stem";
		}
		elsif ($num_pos >= 32 and $num_pos <= 38)
		{
			$location = "Anticodon loop";
		}
		elsif ($num_pos >= 39 and $num_pos <= 43)
		{
			$location = "Anticodon stem";
		}
		elsif ($num_pos >= 44 and $num_pos <= 48)
		{
			$location = "Variable loop";
		}
		elsif ($num_pos >= 49 and $num_pos <= 53)
		{
			$location = "T arm";
		}
		elsif ($num_pos >= 54 and $num_pos <= 60)
		{
			$location = "T-Psi-C loop";
		}
		elsif ($num_pos >= 61 and $num_pos <= 65)
		{
			$location = "T arm";
		}
		elsif ($num_pos >= 66 and $num_pos <= 73)
		{
			$location = "Acceptor stem";
		}
		elsif ($num_pos >= 74 and $num_pos <= 76)
		{
			$location = "CCA";
		}
	}
	
	return $location;
}

sub PrintResultHeader
{
	my ($tdr) = @_;

    print "<BR><BR><BR>\n";
	
	if (scalar(@$tdr) == 0)
	{
		print "<h4>tDR information no found</h4>\n";
	}
	elsif ($ID ne $tdr->[2])
	{
		print "<h4>".$tdr->[2]." (".$ID.")</h4>\n";
	}
	else
	{
		print "<h4>".$tdr->[2]."</h4>\n";
	}
	
	if ($tdr->[14] > 0)
	{
		my $html = qq{
		<ul class="button-group even-2">
			<li><a class="button">Overview</a></li>
		};
		print $html;
		print "\t<li><a href='/cgi-bin/tDRcluster.cgi?run=".$RUN."&id=".$ID."&org=".$ORG."' class='button subnav'>tDR Group</a></li>\n</ul>\n";
	}
}

sub PrintDetails
{
	my ($tdr, $alignments, $mfe_file, $mfe, $sequence, $structure, $png_file) = @_;
	
	my $gtrnadb_link = "http://gtrnadb.ucsc.edu/genomes/".lc($genome_info->{org_domain})."/".$genome_info->{org_abbr}."/genes/";
	
	my $html = qq{
			<div class="panel tab_panel">
			<div class="row">
			<div class="small-12 medium-7 large-8 columns"><div class="panel">
			<table width="100%">
				<tbody>
	};
	print $html;

	my $temp = "";
	print "<tr><td width=15%>Organism</td><td>".$genome_info->{org_name}."</td></tr>\n";
	print "<tr><td width=15%>tDR name <a href=\"/tDRnamer/docs/#standardized-tdr-naming-system\" target=_blank><i class=\"fa fa-info-circle\"></i></a></td><td>".$tdr->[2]."</td></tr>\n";
	if ($tdr->[3] ne "" and $tdr->[3] ne "None")
	{
		$temp = $tdr->[3];
		$temp =~ s/\,/\<br\>/g;
		print "<tr><td width=15%>Synonyms</td><td>".$temp."</td></tr>\n";
	}
	print "<tr><td width=15%>tDR sequence</td><td class=\"seq_text\">&nbsp;&nbsp;&nbsp;<span class=\"alignment_ruler\">";
	for (my $i = 0; $i < $tdr->[5]; $i++)
	{
		if (($i + 1) % 10 == 0)
		{
			print "|";
		}
		else
		{
			print ".";
		}
	}
	print "</span><br>5'&nbsp;".$tdr->[15]."</td></tr>\n";
	print "<tr><td width=15%>tDR sequence length</td><td>".$tdr->[5]."</td></tr>\n";
	$temp = $tdr->[6];
	$temp =~ s/\.\./ to /;
	if (($tdr->[12] ne "None" and $tdr->[1] eq "mature tRNA") or $tdr->[1] eq "pre-tRNA")
	{
		print "<tr><td width=20%>Sprinzl Position <a href=\"https://doi.org/10.1093/nar/21.13.3011\" target=_blank><i class=\"fa fa-info-circle\"></i></a></td><td>".$temp;
		print " (".&GetAlignmentLocation($tdr->[6], $tdr->[1]).")";
		print "</td></tr>\n";
	}
	else
	{
		print "<tr><td width=20%>Position</td><td>".$temp."</td></tr>\n";
	}
	my $label = "Source tRNA";
	my @isodecoders = split(/\,/, $tdr->[4]);
	if (scalar(@isodecoders) > 1)
	{
		$label = "Source tRNAs";
	}
	my @temp_links = ();
	my $link = "";
	for (my $i = 0; $i < scalar(@isodecoders); $i++)
	{
		my $gene = $isodecoders[$i];
		if ($tdr->[1] eq "mature tRNA")
		{
			$gene .= "-1";
		}
		$link = "<a href='".$gtrnadb_link.$gene.".html' target=_blank>".$isodecoders[$i]."</a>";
		push(@temp_links, $link);
	}
	print "<tr><td width=15%>".$label."</td><td>".join("</br>", @temp_links)."</td></tr>\n";
	print "<tr><td width=15%>Source type</td><td>".$tdr->[1]."</td></tr>\n";
	$temp = $tdr->[8];
	$temp =~ s/\,/\, /g;
	print "<tr><td width=15%>Isotype</td><td>".$temp."</td></tr>\n";
	$temp = $tdr->[7];
	$temp =~ s/\,/\, /g;
	print "<tr><td width=15%>Anticodon</td><td>".$temp."</td></tr>\n";
	print "<tr><td width=15%># of mapped isodecoders</td><td>".scalar(@isodecoders)."</td></tr>\n";
	print "<tr><td width=15%># of mismatches</td><td>".$tdr->[9]."</td></tr>\n";
	if ($tdr->[11] ne "None" and $tdr->[11] ne "NA")
	{
		print "<tr><td width=15%>Mismatch positions</td><td>".$tdr->[11]."</td></tr>\n";
	}
	print "<tr><td width=15%># of indels</td><td>".$tdr->[10]."</td></tr>\n";
	
	$html = qq{
				</tbody>
			</table>
			</div>
	};
	print $html;

	$html = qq{
			<div class="panel">
				<h5>Alignments with Source tRNA(s)</h5>
	};
	print $html;
	if (scalar(@$alignments) > 0)
	{		
		print "<pre><div class=\"seq_alignment\">";
		&print_alignments($alignments, $tdr->[scalar(@$tdr)-1]);
		print "</div></pre></div>\n";
	}
	$html = qq {
		<div class='vert-legend'>
		<div class='legend-scale'>
		<ul class='legend-labels'>
			<li><span ID=b5></span>Acceptor stem</li>
			<li><span ID=b1></span>D-stem</li>
			<li><span ID=b2></span>Anticodon stem</li>
			<li><span ID=b6></span>Variable stem</li>
			<li><span ID=b4></span>T-stem</li>
		</ul>
		</div>
		</div>
	};	
	print $html;
	$html = qq{
			</div>
	};
	print $html;

	$html = qq{
			<div class="small-12 medium-5 large-4 columns"><div class="panel">
				<h5>tDR location within tRNA</h5>
	};
	print $html;
	print "<img style='max-width:100%; max-height:100%; background-color:white' src=\"/download/tDRnamer/run$RUN"."/"."$png_file\" alt=\"tDR location\"></img>";
	print "<a href=\"/download/tDRnamer/run$RUN"."/"."$png_file\" class=\"button tiny\" download target=_blank>Save As PNG File</a></li>\n";
	my $ps_file = substr($png_file, 0, rindex($png_file, ".")).".ps";
	print "<a href=\"/download/tDRnamer/run$RUN"."/"."$ps_file\" class=\"button tiny\" download target=_blank>Save As PS File</a></li>\n";
	print "<br><small>Image rendered by NAVIEW</small></div>\n";

	my $mfe_label = "";
	if ($mfe ne "")
	{
		$mfe_label = "Minimum free energy fold: ".$mfe." kcal/mol";
	}
	else
	{
		$mfe_label = "Minimum free energy fold";
	}
	$html = qq{
			<div class="panel">
	};
	print $html;
	print "<h5>".$mfe_label."</h5>\n";
	my $mfe_png_file = substr($mfe_file, 0, length($mfe_file)-3)."png";
	my $mfe_eps_file = substr($mfe_file, 0, length($mfe_file)-3)."eps";
	if ($sequence ne "")
	{
		print "<div id='rna_ss' style='background-color:#fff'></div>\n";
		print "<script type='text/javascript'>\n";
        print "drawMFE(\"#rna_ss\", \"".$sequence."\",\"".$structure."\");\n";
    	print "</script>\n";
	}
	elsif ($mfe_png_file ne "")
	{
		print "<img style='max-width:100%; max-height:100%; background-color:white' src=\"/download/tDRnamer/run$RUN"."/"."$mfe_png_file\" alt=\"Minimum Free Energy Fold by RNAFold\"></img>";
	}
	else
	{
		print "<p style='background-color:white'>Not available</p>\n";
	}
	if (-r $DOWNLOAD_TEMP."/run".$RUN."/".$mfe_png_file and -r $DOWNLOAD_TEMP."/run".$RUN."/".$mfe_eps_file)
	{
		print "<a href=\"/download/tDRnamer/run$RUN"."/"."$mfe_png_file\" class=\"button tiny\" download target=_blank>Save As PNG File</a></li>\n";
		print "<a href=\"/download/tDRnamer/run$RUN"."/"."$mfe_eps_file\" class=\"button tiny\" download target=_blank>Save As EPS File</a></li>\n";
	}

	$html = qq{
				<br><small>Secondary structure predicted by <a href="https://www.tbi.univie.ac.at/RNA/RNAfold.1.html" target=_blank>RNAFold</a><br>
				Image rendered by <a href="http://rna.tbi.univie.ac.at/forna/" target=_blank>forna</a> and <a href="http://varna.lri.fr/" target=_blank>VARNA</a></small>
			</div></div>
		</div></div>
	};
	print $html;
}

sub print_alignments
{    
    my ($alignments, $tDR_name) = @_;
    
    my @posAR = ();
    my @structAR = ();
    my $pair = +{};
    my $block_count = 0;
    my $pair_pos = 0;
    my $last_pos = '';
    my $i = 0;
    my $index = 0;
	my $diff_pos = {};
    
	my $ss = $alignments->[scalar(@$alignments)-1];
	$ss =~ s/</\(/g;
	$ss =~ s/>/\)/g;
	$ss =~ s/_/\./g;
	$ss =~ s/:/\./g;
	$ss =~ s/,/\./g;
	$alignments->[scalar(@$alignments)-1] = $ss;
	chomp($ss);
    @posAR = split(//, $ss);

    for ($index = 0; $index < scalar(@posAR); $index++)
	{
        $pair = +{};
        $structAR[$index] = $pair;
        if ($posAR[$index] eq '(' or $posAR[$index] eq '<') {
            $pair_pos = $index;
            $last_pos = $posAR[$index];
        }
        elsif ($posAR[$index] eq ')' or $posAR[$index] eq '>')
		{
            if (defined $structAR[$pair_pos]->{rev})
			{
#                die ("Invalid secondary structure\n");
            }
            else
			{
                if ($last_pos ne $posAR[$index])
				{
                    $block_count++;
                }
                $structAR[$pair_pos]->{rev} = $index;
                $structAR[$pair_pos]->{block} = $block_count;
                $structAR[$index]->{fwd} = $pair_pos;
                $structAR[$index]->{block} = $block_count;
                for ($i = ($pair_pos - 1); $i >= 0; $i--)
				{
                    if ((!defined $structAR[$i]->{rev}) && ($posAR[$i] eq '(' or $posAR[$i] eq '<'))
					{
                        if ($i < ($pair_pos - 15))
						{
                            $block_count++;
                        }
                        $pair_pos = $i;
                        last;
                    }
                }
                $last_pos = $posAR[$index];
            }
        }
    }

	$ss .= "\n";
	pop(@$alignments);
	unshift(@$alignments, $ss);
	
    foreach my $line (@$alignments)
	{
		chomp($line);
		if (substr($line, 0, index($line, " ")) eq $ID)
		{
			print "<B>";
			$diff_pos = &find_diff_pos($tDR_name, $line);
		}
		if (length($line) > scalar(@structAR))
		{
			print substr($line, 0, length($line) - scalar(@structAR));
		}
		for ($index = 0; $index < scalar(@structAR); $index++)
		{
			if (index($line, " ") == $index and substr($line, 0, index($line, " ")) eq $ID)
			{
		        print "</B>";
			}
			if (defined $structAR[$index]->{block} and substr($line, 0, index($line, " ")) ne $ID)
			{
				my $block_num = $structAR[$index]->{block};
				if ($block_count > 5)
				{
					if ($block_num > ($block_count - 2))
					{
						$block_num = 5 - ($block_count - $block_num);
					}
					elsif ($block_num > 3)
					{
						$block_num = $block_num + ($block_count - 5);
					}
				}

				print "<span ID=b$block_num>" . substr($line, $index, 1) . "</span>";
			}
			elsif (substr($line, 0, index($line, " ")) eq $ID)
			{
				if (defined $diff_pos->{$index})
				{
					print "<span ID=diff_pos>" . substr($line, $index, 1) . "</span>";
				}
				else
				{
					print substr($line, $index, 1);
				}
			}
			else
			{
				print substr($line, $index, 1);
			}
		}		
        print "\n";
    }
}

sub find_diff_pos
{
	my ($tDR_name, $tDR_alignment) = @_;
	my $pos = 0;
	my $indel_len = 0;
	my $start = rindex($tDR_alignment, " ")+1;
	my $delete = 0;
	my $base_count = 0;
	my %diff_pos = ();

	my @parts = split(/\-/, $tDR_name);
	for (my $i = 5; $i < scalar(@parts); $i++)
	{
		if ($parts[$i] =~ /^[ACGU](\d+)[ACGU]$/)
		{
			$pos = $1;
		}
		elsif ($parts[$i] =~ /^I(\d+)([ACGU]+)$/)
		{
			$pos = $1;
			$indel_len = length($2);
		}
		elsif ($parts[$i] =~ /^D(\d+)([ACGU]+)$/)
		{
			$pos = $1;
			$indel_len = length($2);
			$delete = 1;
		}
		else
		{
			$pos = 0;
		}
		if ($pos > 0)
		{			
			for (my $j = $start; $j < length($tDR_alignment); $j++)
			{
				if (substr($tDR_alignment, $j, 1) =~ /[ACGU]/)
				{
					$base_count++;
				}
				if ($base_count == $pos)
				{
					if ($indel_len == 0)
					{
						$diff_pos{$j} = 1;
					}
					else
					{
						if ($delete)
						{
							$j++;
						}
						for (my $k = 0; $k < $indel_len; $k++)
						{
							$diff_pos{$j} = 1;
							if ($k < ($indel_len - 1))
							{
								$j++;
							}
						}
					}
					$start = $j+1;
					last;
				}
			}
			$delete = 0;
			$indel_len = 0;
		}
	}

	return \%diff_pos;
}

sub min
{
	my ($a, $b) = @_;
	my $value = $a;
	if ($b < $value)
	{
		$value = $b;
	}
	return $value;
}

sub trim
{
	my ($str) = @_;
	$str =~ s/^\s+|\s+$//g;
	return $str;
}

sub End_HTML_Page 
{
    &HTMLFoot;
#    print "</body></html>\n";
    if ($NETSCAPE) { print "\n--NewData--\n"; }
}

# Report CGI Errors specified in variable $ERROR

sub CGI_Error 
{
    $Title = "CGI Error";
    &HTML_Header;

    print "$ERROR",
    "</BODY>\n",
    "</HTML>\n";

    if ($NETSCAPE == 1) { print "\n--NewData--\n"; }

    &exit_signal;
}

# Sorting Algorithm (Sort by Seqf Coords)

sub HTML_Header 
{
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

sub Insert_Queue 
{
    open (QUEUE, ">>$QUEUE_FILE");
#    flock (QUEUE, 2);
    print (QUEUE "W $PID $est_time\n");
#    flock (QUEUE, 8);
    close (QUEUE);
}


sub Wait_Turn 
{
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

sub Is_Process_Alive 
{
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

sub Remove_Queue 
{
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

sub Wait_Notice 
{
    if ($METHOD eq 'mail') { return; }

    $Title = "tDRdetails Queue";
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

sub exit_signal 
{
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

sub exit_parent 
{
	exit(0);
}

sub kill_child 
{
    kill('USR1', $child);
    exit(1);
}

sub Error_Handler
{
}

