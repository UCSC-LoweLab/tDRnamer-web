#! /usr/bin/perl

# CGI library for tDRnamer web server
# 
# To generate a header, you call two functions: 
#   the generic Genetics header, and then a subsection-specific
#   navigation bar.
#
#   example: 
#         &HTMLHead("Generic title", "Dept. of Genetics", "Test page",
#                           "This is a test page");
# 
# To generate a footer, there is one function:
#        &HTMLFoot;

sub read_configuration_file
{
	my $conf_file = "tDRnamer.conf";
	my $line = "";
    my ($key, $value, $temp, $key2, $value2, $subkey1, $subkey2, $index);
	my %configurations = ();

	open (FILE_IN, "$conf_file") || die "Fail to open configuration file $conf_file.";
    while ($line = <FILE_IN>)
    {
        chomp($line);
        if ($line !~ /^#/)
        {
            if ($line =~ /^(\S+):\s+(.+)\s*$/)
            {
                $key = $1;
                $value = $2;
                $temp = $value;
                $index = index($temp, "}");
                while ($index > -1)
                {
                    $key2 = substr($temp, index($temp,"{") + 1, $index - index($temp,"{") - 1);
                    $value2 = $configurations{$key2};
                    $value =~ s/{$key2}/$value2/;
                    $temp = substr($temp, $index + 1);
                    $index = index($temp, "}");
                }
                
				if (index($value, "\$\$") > -1)
				{
					$temp = "$$";
					$value =~ s/\$\$/$temp/;
				}
				
                if ($key =~ /^(\S+)\.(\S+)/)
                {
                    $subkey1 = $1;
                    $subkey2 = $2;
                    $configurations{$subkey1}->{$subkey2} = $value;
                }
                else
                {
					if ($key eq "temp_dir" and defined $configurations{$key}) {}
					else
					{
						$configurations{$key} = $value;
					}
                }
            }
        }
    }
    close (FILE_IN);

	return \%configurations;
}

sub check_input
{
	my ($in) = @_;
	my $valid = 1;
	my $key = "";
	my $value = "";
	
	if (defined $in->{'qformat'} and $in->{'qformat'} ne "raw" and $in->{'qformat'} ne "formatted")
	{
		$key = "qformat";
		$value = $in->{'qformat'};
		$valid = 0;
	}
	if (defined $in->{'organism'} and $in->{'organism'} !~ /^[\w\.\-]+$/)
	{
		$key = "organism";
		$value = $in->{'organism'};
		$valid = 0;
	}
	if (defined $in->{'seqname'} and $in->{'seqname'} ne "" and $in->{'seqname'} !~ /^[\w\-\:]+$/)
	{
		$key = "seqname";
		$value = $in->{'seqname'};
		$valid = 0;
	}
	if (defined $in->{'qseq'} and $in->{'qseq'} ne "" and $in->{'qseq'} =~ /[\<\%\$\#]+/)
	{
		$key = "qseq";
		$value = $in->{'qseq'};
		$valid = 0;
	}
	if (defined $in->{'qname'} and $in->{'qname'} ne "" and $in->{'qname'} !~ /^[\w\:\+\-\r\n]+$/)
	{
		$key = "qname";
		$value = $in->{'qname'};
		$valid = 0;
	}
	if (defined $in->{'seqfile'} and $in->{'seqfile'} ne "" and $in->{'seqfile'} =~ /[\<\%\$\#]+/)
	{
		$key = "seqfile";
		$value = $in->{'seqfile'};
		$valid = 0;
	}
	if (defined $in->{'namefile'} and $in->{'namefile'} ne "" and $in->{'namefile'} =~ /[\<\%\$\#]+/)
	{
		$key = "namefile";
		$value = $in->{'namefile'};
		$valid = 0;
	}
	if (defined $in->{'address'} and $in->{'address'} ne "" and $in->{'address'} =~ /[\<\>\n\%\$\#]+/)
	{
		$key = "address";
		$value = $in->{'address'};
		$valid = 0;
	}
	if (defined $in->{'searchType'} and $in->{'searchType'} ne "" and ($in->{'searchType'} ne "sequence" and $in->{'searchType'} ne "name"))
	{
		$key = "searchType";
		$value = $in->{'searchType'};
		$valid = 0;
	}
	if (defined $in->{'run'} and $in->{'run'} !~ /^\d+_\d+$/)
	{
		$key = "run";
		$value = $in->{'run'};
		$valid = 0;
	}
	if (defined $in->{'id'} and $in->{'id'} !~ /^[\w\-\:]+$/)
	{
		$key = "id";
		$value = $in->{'id'};
		$valid = 0;
	}
	if (defined $in->{'org'} and $in->{'org'} !~ /^[\w\.\-]+$/)
	{
		$key = "org";
		$value = $in->{'org'};
		$valid = 0;
	}
	return ($valid, $key, $value);
}

sub Read_genome_info 
{    
    my ($genome_info_file, $ref_genomes_info, $fix_name) = @_;
    
    my $line = "";
    my @columns = ();
    my @headings = ();
    my $genome = +{};
    my $i = 0;
    open (FILE_IN, "$genome_info_file") ||
    die "Fail to open $genome_info_file\n";
    
    $line = <FILE_IN>;
    chomp($line);
    @headings = split(/\t/, $line);
    while ($line = <FILE_IN>)
	{
        chomp($line);
		if ($line !~ /^#/)
		{
			@columns = split(/\t/, $line);
			if ($fix_name)
			{
				$columns[0] = &fix_org_name($columns[0], $columns[3]);
			}
			$genome = +{};
			for ($i = 0; $i < scalar(@headings); $i++)
			{
				if (!$fix_name)
				{
					$columns[$i] =~ s/ /_/g;
					if (index($columns[$i], "_(") > 0)
					{
						$columns[$i] = substr($columns[$i], 0, index($columns[$i], "_("));
					}
				}
				$genome->{$headings[$i]} = $columns[$i];
			}
			$ref_genomes_info->{$columns[0]} = $genome;
		}
    }
    
    close FILE_IN;
}

sub Get_genome_info
{
	my ($genome_info_file, $org_db) = @_;

    my @columns = ();
    my $genome = +{};

	my $cmd = "grep \"".$org_db."\" ".$genome_info_file;
	my @lines = split(/\n/, `$cmd`);

	$cmd = "head -n 1 ".$genome_info_file;	
    my $line = `$cmd`;
	chomp($line);
	my @headings = split(/\t/, $line);

	for (my $i = 0; $i < scalar(@lines); $i++)
	{
		$line = $lines[$i];
        chomp($line);
		if ($line !~ /^#/)
		{
			@columns = split(/\t/, $line);

			if ($columns[2] eq $org_db)
			{
				for ($i = 0; $i < scalar(@headings); $i++)
				{
					$genome->{$headings[$i]} = $columns[$i];
				}	
				last;			
			}
		}
    }
    
    close FILE_IN;

	return $genome;
}

sub Read_browser_db
{
	my ($browser_db_file, $browser_db_list) = @_;
    
    my $line = "";
    open (FILE_IN, "$browser_db_file") ||
    die "Fail to open $browser_db_file\n";
    
    $line = <FILE_IN>;
    while ($line = <FILE_IN>)
	{
        chomp($line);
		if ($line !~ /^#/)
		{
			$browser_db_list->{$line} = 1;
		}
    }
    
    close FILE_IN;
}

sub fix_org_name
{
	my ($org_name, $domain) = @_;

	if ($domain eq "Eukaryota")
	{
		my $index = index($org_name, " (");
		if ($index > -1)
		{
			$org_name = substr($org_name, 0, $index);
		}
	}
	
	$org_name =~ s/\.//g;
	$org_name =~ s/\(//g;
	$org_name =~ s/\)//g;
	$org_name =~ s/=//g;
	$org_name =~ s/\'//g;
	$org_name =~ s/\[//g;
	$org_name =~ s/\]//g;
	$org_name =~ s/:/_/g;
	$org_name =~ s/\,/_/g;
	$org_name =~ s/_- / /g;
	$org_name =~ s/  / /g;
	$org_name =~ s/ /_/g;

	return $org_name;
}

sub Get_trna_coords 
{    
    my ($gtrnadb_id, $json_file) = @_;

    my $line = "";
	my $match = 0;
	my $locus = "";
    
    if (open (FILE_IN, "$json_file"))
    {    
		while ($line = <FILE_IN>)
		{
			chomp($line);
			if ($line =~ /\"GtRNAdbID\": \"(.+)\"\,/)
			{
				if ($gtrnadb_id eq $1)
				{
					$match = 1;
				}
			}
			elsif ($line =~ /\"locus\": \"(.+)\"\,/)
			{
				if ($match)
				{
					$locus = $1;
					$locus = substr($locus , 0, index($locus, " ("));
					last;
				}
			}
		}
    
		close FILE_IN;
    }
    return ($locus);
}

# HTMLHead()
# Generate the HTML header, local logo, titles, and navigation bar.
#
sub HTMLHead 
{
    local($title, $google_analytics) = @_;
    print <<END;
Content-type: text/html

<html class="no-js" lang="en">
	<head>
<!-- Global site tag (gtag.js) - Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=$google_analytics"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', '$google_analytics');
</script>

		<meta charset="utf-8">

		<!-- Always force latest IE rendering engine (even in intranet) & Chrome Frame
		Remove this if you use the .htaccess -->
		<meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">

		<title>tDRnamer</title>
		<meta name="description" content="tDRnamer 1.0">
		<meta name="author" content="Andrew D. Holmes, Patricia P. Chan, and Todd M. Lowe">

		<meta name="viewport" content="width=device-width, initial-scale=1.0">

		<!-- Replace favicon.ico & apple-touch-icon.png in the root of your domain and delete these references -->
		<link rel="shortcut icon" href="/favicon.ico">
		<link rel="apple-touch-icon" href="/apple-touch-icon.png">
		<link rel="stylesheet" href="../tDRnamer/style/normalize.css">
		<link rel="stylesheet" href="../tDRnamer/style/foundation.css">
		<link rel="stylesheet" href="../tDRnamer/style/tdrnamer.css">
		<link rel="stylesheet" id="font-awesome-css" href="../tDRnamer/style/font-awesome-4.3.0/css/font-awesome.min.css">
		<link rel="stylesheet" type="text/css" href="../tDRnamer/style/jquery.dataTables.css">
		<link rel="stylesheet" type="text/css" href="../tDRnamer/style/dataTables.foundation.css">
    	<link rel='stylesheet' type='text/css' href="../tDRnamer/style/fornac.css">
		<script src="../tDRnamer/js/vendor/modernizr.js"></script>
		<script src="../tDRnamer/js/vendor/jquery.js"></script>
	  	<script src="../tDRnamer/js/vendor/jquery.dataTables.min.js"></script>
	  	<script src="../tDRnamer/js/vendor/dataTables.foundation.js"></script>
	    <script type='text/javascript' src="../tDRnamer/js/fornac.js"></script>
	    <script type='text/javascript' src="../tDRnamer/js/tDRresult.js"></script>
  	</head>

	<body>

<!--small off canvas menu-->
<div class="off-canvas-wrap" data-offcanvas>
	<div class="inner-wrap">

<!--top menu-->
<nav class="tab-bar show-for-small">
	<a class="left-off-canvas-toggle menu-icon ">
		<span>Home</span>
	</a>  
</nav>

<nav class="top-bar hide-for-small" data-topbar>
	<ul class="title-area">
		<li class="name">
			<h1><a href="../tDRnamer/index.html">Home</a></h1>
		</li>
	</ul>

	<section class="top-bar-section">
		<ul class="right">
			<li class="divider"></li>
			<li><a href="../tDRnamer/docs/" target=_blank>User Guide</a></li>
			<li class="divider"></li>
<!--			<li><a href="../tDRnamer/citation.html">Citation</a></li>-->
			<li><a href="../tDRnamer/contact.html">Contact Us</a></li>
		</ul>
	</section>
</nav>

<aside class="left-off-canvas-menu">

<ul class="off-canvas-list">
	<li><label class="first">tDRnamer</label></li>
	<li><a href="../tDRnamer/index.html">Home</a></li>
</ul>

<hr>

<ul class="off-canvas-list">
    <li><label>Help</label></li>
    <li><a href="docs/" target=_blank>User Guide</a></li>
</ul>

<hr>

<ul class="off-canvas-list">
    <li><label>About</label></li>
<!--	<li><a href="citation.html">Citation</a></li>-->
    <li><a href="contact.html">Contact Us</a></li>
    <li><a href="http://lowelab.ucsc.edu" target=_blank>Lowe Lab</a></li>
</ul>

</aside>

<!--content-->
<!--title-->
<header id="page-header">	  
	<div class="small-10 medium-7 large-4 columns">
		<img src="../tDRnamer/image/tDRnamer_with_name.png"/>
	</div>
	<div class="small-10 medium-7 large-4 columns">
		<h5>$title</h5>
	</div>
</header>

<div class="scroll-top-wrapper ">
	<span class="scroll-top-inner">
		<i class="fa fa-2x fa-arrow-up"></i>
	</span>
</div>

<section id="genome-section">	

END
}

# HTMLFoot()
# Generate the standard footer of a page.
sub HTMLFoot 
{        
    print <<END;
</section>
	
<section id="footer">
	<div class="row">
		<div class="small-12 columns">
			<p><a href="http://lowelab.ucsc.edu" target=_blank>The Lowe Lab</a>, Biomolecular Engineering, University of California Santa Cruz</p>
		</div>
	</div>
</section>

		<a class="exit-off-canvas"></a>
	</div>      
</div>
		
		<script src="../tDRnamer/js/backToTop.js"></script>
	  	<script src="../tDRnamer/js/foundation.min.js"></script>
	  	<script type="text/javascript">
	    $(document).foundation();
	  	</script>
	</body>
</html>
END
}

1;
