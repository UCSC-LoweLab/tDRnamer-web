#! /usr/bin/perl

require "cgi-lib.pl";
require "tDRnamer-wwwlib.pl";

#*****************************************************************************************
#
# tDRcluster.cgi by Patricia Chan and Todd Lowe
#
# CGI script that displays cluster info for tDRnamer web server
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
	print "<!-- Are you there? -->\n";

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
    $LOG_FILE = "$TEMP/tDRnamer_cluster.log";

    #Queue Files for tDR cluster search
    $QUEUE_FILE = "$TEMP/tDRnamer_cluster_Queue";

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

    #Message for e-mail request

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
    my ($clusters, $source, $position) = &Get_cluster($tdr);
	my $members_tDR_names = &Get_tDR_names($clusters);
	if ($source eq "pre-tRNA")
	{
		$clusters = &Adjust_pre_tDR_alignments($clusters);
	}
#	for (my $i = 0; $i < scalar(@$clusters); $i++)
#	{
#		$clusters->[$i]->{alignment} = &Remove_alignment_gaps($clusters->[$i]->{alignment});
#	}

    #Get finishing time.
    $finish_time = time;

    #HTML Search Output 
    #Output to the browser (before timeout).

	# Print out the beginning of the HTML Page for the output
	&Start_HTML_Page;

	# Print out the results
	&PrintResultHeader($tdr);
	&PrintCluster($clusters, $source, $position, $members_tDR_names);

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

	print (LOG "$date tDRcluster TIME: $total_time ",
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

sub Get_tDR_names
{
	my ($clusters) = @_;
	my $cluster = "";
	my $source = "";
	my $position = "";
	my $info_file = $DOWNLOAD_TEMP."/run".$RUN."/seq".$PREFIX."-tDR-info.txt";
	my $found = 0;
	my $line = "";
	my @columns = ();
	my %member_tDR_names = ();

	for (my $i = 0; $i < scalar(@$clusters); $i++)
	{
		my @members = sort (split(/\,/, $clusters->[$i]->{members}));
		for (my $j = 0; $j < scalar(@members); $j++)
		{
			if (!defined $member_tDR_names{$members[$j]})
			{
				$member_tDR_names{$members[$j]} = "";
			}
		}
	}

	open(FILE_IN, "$info_file") or die "Fail to open $info_file\n";
	while (($line = <FILE_IN>) and !$found)
	{
		@columns = split(/\t/, $line);
		if (defined $member_tDR_names{$columns[0]})
		{
			$member_tDR_names{$columns[0]} = $columns[2];
		}
	}
	close(FILE_IN);
	
	return \%member_tDR_names;
}

sub Get_cluster
{
	my ($tdr) = @_;
	my $cluster_str = $tdr->[13];
	my $source = $tdr->[1];
	my $position = $tdr->[6];

	my @cluster_ids = ();
	if (index($cluster_str, ",") > -1)
	{
		@cluster_ids = sort {$a <=> $b} (split(/\,/, $cluster_str));
	}
	else
	{
		push(@cluster_ids, int($cluster_str));
	}

	my @clusters = ();
	my $cluster = {};
	my $start = 0;
	my $coverage = 0;
	my $alignment = 0;
	my $alignments = [];
	my $coverages = [];
	
	my $cluster_file = $DOWNLOAD_TEMP."/run".$RUN."/seq".$PREFIX."-tDR-groups.txt";
	my $line = "";
	my $i = 0;
	open(FILE_IN, "$cluster_file") or die "Fail to open $cluster_file\n";
	while (($line = <FILE_IN>) and ($i < scalar(@cluster_ids)))
	{
		chomp($line);
		if ($line =~ /^tDR Group (\d+): (.+)$/)
		{
			if (defined $cluster->{id})
			{
				push(@clusters, $cluster);
			}			
			if ($cluster_ids[$i] == $1)
			{
				$cluster = {};
				$cluster->{members} = $2;
				$cluster->{id} = $cluster_ids[$i];
				$start = 1;
			}
			else
			{
				$start = 0;
			}
			$coverage = 0;
			$alignment = 0;
		}
		elsif ($line =~ /^tDR Singleton (\d+): (.+)$/)
		{
			if (defined $cluster->{id})
			{
				push(@clusters, $cluster);
			}			
			if ($cluster_ids[$i] == $1)
			{
				$cluster = {};
				$cluster->{members} = $2;
				$cluster->{id} = $cluster_ids[$i];
				$i++;
			}					
			$start = 0;
			$coverage = 0;
			$alignment = 0;
		}
		elsif ($line eq "//")
		{
			if ($start == 1)
			{
				$start = 0;
				$i++;
			}
		}
		elsif ($start and $line eq "tDR Location")
		{
			$coverage = 1;
			$coverages = [];
			$cluster->{coverage} = $coverages;
		}
		elsif ($start and $line eq "tDR Isotype(s)")
		{
			$coverage = 0;
			$line = <FILE_IN>;
			chomp($line);
			my $isotypes = [];
			@$isotypes = split(/\,/, $line);
			$cluster->{isotypes} = $isotypes;
		}
		elsif ($start and $line eq "tDR Alignment")
		{
			$coverage = 0;
			$alignment = 1;
			$alignments = [];
			$cluster->{alignment} = $alignments;
		}
		elsif ($start and $coverage)
		{
			push(@{$cluster->{coverage}}, $line);
		}
		elsif ($start and $alignment)
		{
			if ($line ne "# STOCKHOLM 1.0" and index($line, "#=GC RF") == -1)
			{
				push(@{$cluster->{alignment}}, $line);
			}
			elsif (index($line, "#=GC RF") > -1)
			{
				$cluster->{RF} = $line;
			}
		}
	}
	close(FILE_IN);
	if (defined $cluster->{id})
	{
		push(@clusters, $cluster);
	}
	
	return (\@clusters, $source, $position);
}

sub Adjust_pre_tDR_alignments
{
	my ($clusters) = @_;
	
	for (my $i = 0; $i < scalar(@$clusters); $i++)
	{
		my @alignments = @{$clusters->[$i]->{alignment}};
		my @mod_alignments = ("") x scalar(@alignments);
		my $left_start = 0;
		my $right_end = 0;
		my $align_len = 0;
		my $nt_ct = 0;
		my $start_member = 0;
		my $gap = 1;
		my $tRNA_start = 0;
		my $tRNA_end = 0;
		my $tail_start = length($alignments[(scalar(@alignments)-1)]);

		my ($seq_name, $align, $dummy);
		my @members = sort (split(/\,/, $clusters->[$i]->{members}));
		for (my $j = 0; $j < scalar(@alignments); $j++)
		{
			($seq_name, $align, $dummy) = split(/\s+/, $alignments[$j]);
			if (&bsearch_members($seq_name, \@members) > -1)
			{
				$start_member = $j;
				last;
			}
		}
		
		my $start_pos = index($alignments[(scalar(@alignments)-1)], " :") + 1;
		$left_start = $start_pos;
		$right_end = index($alignments[(scalar(@alignments)-1)], ": ");
	
		for (my $m = $start_pos; $m < $tail_start; $m++)
		{
			if (substr($clusters->[$i]->{RF}, $m, 1) ne ".")
			{
				if ($tRNA_start == 0)
				{
					$tRNA_start = $m;
				}
				else
				{
					$tRNA_end = $m;
				}
			}
		}

		for (my $k = $start_pos; $k < $tail_start; $k++)
		{
			$gap = 1;
			for (my $j = $start_member; $j < (scalar(@alignments) - 1); $j++)
			{
				if (substr($alignments[$j], $k, 1) ne ".")
				{
					$gap = 0;
				}
			}
			if (substr($alignments[(scalar(@alignments)-1)], $k, 1) eq ":" and 
				($k < $tRNA_start or $k > $tRNA_end))
			{
				if ($gap)
				{
					if ($align_len == 0)
					{
						$left_start = $k;
					}
					elsif ($nt_ct > 0)
					{
						$right_end = $k;
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
				if (!$gap)
				{
					$nt_ct++;
				}	
			}
		}
		
		for (my $j = 0; $j < scalar(@alignments); $j++)
		{
			$mod_alignments[$j] = substr($alignments[$j], 0, $start_pos);
			if ($j < $start_member)
			{
				my $prefix_seq = 1;
				for (my $k = $left_start+1; $k < $tRNA_start; $k++)
				{
					if (substr($alignments[$j], $k, 1) eq "N" and $prefix_seq)
					{
						$mod_alignments[$j] .= "-";
					}
					else
					{
						$prefix_seq = 0;
						$mod_alignments[$j] .= substr($alignments[$j], $k, 1);
					}
				}
				$mod_alignments[$j] .= substr($alignments[$j], $tRNA_start, $tRNA_end-$tRNA_start+1);
				$prefix_seq = 1;
				my $tail_flank = "";
				for (my $k = ($right_end-1); $k >= ($tRNA_end+1); $k--)
				{
					if (substr($alignments[$j], $k, 1) eq "N" and $prefix_seq)
					{
						$tail_flank = "-".$tail_flank;
					}
					else
					{
						$prefix_seq = 0;
						$tail_flank = substr($alignments[$j], $k, 1).$tail_flank;
					}
				}
				$mod_alignments[$j] .= $tail_flank;
			}
			else
			{
				$mod_alignments[$j] .= substr($alignments[$j], $left_start+1, $right_end-$left_start-1);
			}
			if ($j < (scalar(@alignments)-1))
			{
				$mod_alignments[$j] .= substr($alignments[$j], $tail_start);
			}
			else
			{
				$mod_alignments[$j] .= "\n";
			}
		}
		
		@{$clusters->[$i]->{alignment}} = @mod_alignments;
	}
	
	return $clusters;
}

sub Remove_alignment_gaps
{
	my ($alignments) = @_;
	my $gap_count = 0;
	my @new_alignments = ();

	for (my $i = 0; $i < length($alignments->[0]); $i++)
	{
		$gap_count = 0;
		for (my $j = 0; $j < (scalar(@$alignments) - 1); $j++)
		{
			if (substr($alignments->[$j], $i, 1) eq "-" or substr($alignments->[$j], $i, 1) eq ".")
			{
				$gap_count++;
			}
		}
		if ($gap_count < (scalar(@$alignments) - 1))
		{
			for (my $j = 0; $j < scalar(@$alignments); $j++)
			{
				$new_alignments[$j] .= substr($alignments->[$j], $i, 1);
			}
		}
	}
	for (my $j = 0; $j < scalar(@$alignments); $j++)
	{
		if (length($alignments->[$j]) > length($alignments->[0]))
		{
			$new_alignments[$j] .= substr($alignments->[$j], length($alignments->[0]));
		}
	}

	return \@new_alignments;
}

sub bsearch_members
{
    my ($x, $a) = @_;
    my ($l, $u) = (0, @$a - 1);  
    my $i;                       
    while ($l <= $u)
	{
		$i = int(($l + $u)/2);
		if ($a->[$i] lt $x)
		{
			$l = $i+1;
		}
		elsif ($a->[$i] gt $x)
		{
			$u = $i-1;
		} 
		else
		{
			return $i;
		}
    }
    return -1;         
}

sub Start_HTML_Page {

    &HTMLHead("tDR Group", $google_analytics);
}

sub GetAlignmentPosition
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

sub GetAlignmentLocation
{
	my ($location_code, $source) = @_;
	my $location = "";
	
	my $start = substr($location_code, 0, index($location_code, "_"));
	if ($start eq "CCA")
	{
		$location = "CCA tail";
	}
	else
	{
		$start = substr($location_code, 0, 1);
		if ($start eq "A")
		{
			$location = "Acceptor stem";
		}
		elsif ($start eq "D")
		{
			$location = "D arm";
		}
		elsif ($start eq "C")
		{
			$location = "Anticodon stem";
		}
		elsif ($start eq "T")
		{
			$location = "T stem";
		}
		elsif ($start eq "Z")
		{
			$location = "Acceptor stem";
		}
		elsif ($start eq "3")
		{
			$location = "3' trailer";
		}
		elsif ($start eq "5")
		{
			$location = "5' leader";
		}
		elsif ($start eq "V")
		{
			$location = "Variable loop";
		}
	}
	
	my $end = substr($location_code, rindex($location_code, "_")+1);
	if ($end eq "CCA")
	{
		$location .= " to CCA tail";
	}
	else
	{
		$end = substr($end, 0, 1);
		if ($end eq "A")
		{
			$location .= " to Acceptor stem";
		}
		elsif ($end eq "D")
		{
			$location .= " to D arm";
		}
		elsif ($end eq "C")
		{
			$location .= " to Anticodon stem";
		}
		elsif ($end eq "T")
		{
			$location .= " to T stem";
		}
		elsif ($end eq "Z")
		{
			$location .= " to Acceptor stem";
		}
		elsif ($end eq "3")
		{
			$location .= " to 3' trailer";
		}
		elsif ($end eq "5")
		{
			$location .= " to 5' leader";
		}
		elsif ($end eq "V")
		{
			$location .= " to Variable loop";
		}
	}
	
	if ($location eq "" and $source eq "pre-tRNA")
	{
		$location = "Pre-tRNA";
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
		};
		print $html;
		print "\t<li><a href='/cgi-bin/tDRdetails.cgi?run=".$RUN."&id=".$ID."&org=".$ORG."' class='button subnav'>Overview</a></li>\n";
		$html = qq{
			<li><a class="button">tDR Group</a></li>
		</ul>
		};
		print $html;
	}
}

sub PrintCluster
{
	my ($clusters, $source, $position, $members_tDR_names) = @_;
	my $gtrnadb_link = "http://gtrnadb.ucsc.edu/genomes/".lc($genome_info->{org_domain})."/".$genome_info->{org_abbr}."/genes/";
	
	my $html = qq{
			<div class="panel tab_panel">
			<div class="row">
	};
	print $html;
	
	for (my $i = 0; $i < scalar(@$clusters); $i++)
	{
		if ($i > 0)
		{
			print "<br><HR><br>\n";
		}
		print "<h5 style='padding-left:20px'>Group ID: ".$clusters->[$i]->{id}."</h5>\n";

		my $html = qq{
				<div class=\"small-12 medium-6 large-6 columns\"><div class="panel">
				<h5>Other tDRs in group</h5>
				<table width="100%">
					<tbody>
		};
		print $html;
		my @all_members = split(/\,/, $clusters->[$i]->{members});
		my @members = ();
		for (my $k = 0; $k < scalar(@all_members); $k++)
		{
			if ($all_members[$k] ne $ID)
			{
				push(@members, $all_members[$k]);
			}
		}
		my $member_str = "";
		for (my $k = 0; $k < int(scalar(@members) / 2 + 0.99); $k++)
		{
			print "<tr>";
			for (my $j = ($k * 2); $j < &min(scalar(@members), ($k + 1) * 2); $j++)
			{
				my $tDR_name = "";
				if (defined $members_tDR_names->{$members[$j]})
				{
					$tDR_name = $members_tDR_names->{$members[$j]};
				}
				$member_str = "<a href='/cgi-bin/tDRdetails.cgi?run=".$RUN."&id=".$members[$j]."&org=".$ORG."' target=_blank>".$tDR_name." (".$members[$j].")</a>";
				print "<td width=50%>".$member_str."</td>\n";
			}
			if (($k == int(scalar(@members) / 2 + 0.99) - 1) and (scalar(@members) % 2 == 1))
			{
				print "<td width=50%>&nbsp;</td>\n";
			}
			print "</tr>";
		}
		$html = qq{
					</tbody>
				</table>
				</div>
		};
		print $html;
		
		if (defined $clusters->[$i]->{isotypes})
		{
			my $isptypes = join(", ", @{$clusters->[$i]->{isotypes}});
			$html = qq{
				<div class="panel">
					<h5>tRNA isotype(s)</h5>
					<table width="100%">
						<tbody>
							<tr>
								<td>$isptypes</td>
							</tr>
						</tbody>
					</table>
					</div></div>
			};
			print $html;
		}

		if (defined $clusters->[$i]->{coverage})
		{		
			$html = qq{
				<div class=\"small-12 medium-6 large-6 columns\"><div class="panel">
					<h5>tRNAs in group</h5>
					<table width="100%">
						<thead>
						<tr><th width=33.32%>tRNAs</th><th>tDR alignment region</th></tr>
						</thead>
						<tbody>
			};
			print $html;
			for (my $j = 0; $j < scalar(@{$clusters->[$i]->{coverage}}); $j++)
			{
				my ($gene, $location) = split(/:/, $clusters->[$i]->{coverage}->[$j]);
				my @parts = split(/\-/, $gene);
				my $link = $link = "<a href='".$gtrnadb_link.$gene.".html' target=_blank>".$gene."</a>";
				if (scalar(@parts) == 4)
				{
					$link = "<a href='".$gtrnadb_link.$gene."-1.html' target=_blank>".$gene."</a>";
				}
#				print "<tr><td>".$gene."</td><td>".&GetAlignmentLocation($location, $source)."</td></tr>";
				print "<tr><td>".$link."</td><td>".&GetAlignmentPosition($position, $source)."</td></tr>";
			}
			$html = qq{
						</tbody>
					</table>
					</div></div>
			};
			print $html;
		}
		
		if (defined $clusters->[$i]->{alignment})
		{		
			$html = qq{
				<div class=\"small-12 medium-12 large-12 columns\"><div class="panel">
					<h5>Alignments of tDRs and source tRNAs</h5>
			};
			print $html."\n";
			print "<pre><div class=\"seq_alignment\">";
			&print_alignments($clusters->[$i]->{alignment}, scalar(@members)+1);
			print "</div></pre></div>\n";
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
				</div></div>
			};	
			print $html;
		}
		else
		{
			print "<p>This tDR does not group with other tDRs. Please click on the tDR link aboue for more details.</p>\n";
		}
	}
	print "</div></div>\n";
}

sub print_alignments
{    
    my ($alignments, $tDR_count) = @_;
    
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
	$ss = " " x (rindex($ss, " ") + 1).substr($ss, rindex($ss, " ")+1);
	$ss =~ s/</\(/g;
	$ss =~ s/>/\)/g;
	$ss =~ s/_/\./g;
	$ss =~ s/:/\./g;
	$ss =~ s/,/\./g;
	$alignments->[scalar(@$alignments)-1] = $ss;
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

	pop(@$alignments);
	unshift(@$alignments, $ss);
	
	my $cnt = 0;
    foreach my $line (@$alignments)
	{
		if (substr($line, 0, index($line, " ")) eq $ID)
		{
			print "<B>";
		}
		for ($index = 0; $index < scalar(@structAR); $index++)
		{
			if (defined $structAR[$index]->{block})
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
				if ($cnt < (scalar(@$alignments) - $tDR_count))
				{
					print "<span ID=b$block_num>" . substr($line, $index, 1) . "</span>";
				}
				else
				{
					print "<span ID=b".$block_num."_1>" . substr($line, $index, 1) . "</span>";
				}
			}
			else
			{
				print substr($line, $index, 1);
			}
		}
		if (length($line) > scalar(@structAR))
		{
			print substr($line, scalar(@structAR));
		}
		if (substr($line, 0, index($line, " ")) eq $ID)
		{
			print "</B>";
		}		
        print "\n";
		$cnt++;
    }
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

sub End_HTML_Page {
    &HTMLFoot;
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

    if ($NETSCAPE == 1) { print "\n--NewData--\n"; }

    &exit_signal;

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
	    print "<!-- Are you there? -->\n"; 
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

    $Title = "tDRcluster Queue";
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
		print (LOG "$date tDRcluster stopped TIME: $total_time ",
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

