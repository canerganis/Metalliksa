NIST Data Publication:
Single-track laser scan cross-sectional micrographs on IN625 and IN718 bare plates with melt pool depth and width measurements
Version 1.0.0
https://doi.org/10.18434/mds2-2923

Authors:
  Jordan S. Weaver
    National Institute of Standards and Technology
    Intelligent Systems Division
  David Deisenroth
    National Institute of Standards and Technology
    Intelligent Systems Division 
  Sergey Mekhontsev
    National Institute of Standards and Technology
    Intelligent Systems Division
  Jarred Heigel
    ATA Engineering, Inc.
  Brandon Lane
    National Institute of Standards and Technology
    Intelligent Systems Division

Contact:
  Jordan Weaver
    jordan.weaver@nist.gov

Description:

Single-track laser scans were produced with Yb-fiber lasers on bare plates of IN625 and IN718 using three different laser powder bed fusion machines. The laser power, scan speed, and laser spot diameter varied. Tracks were cross-sectioned and metallographically prepared. Optical micrographs were taken on etched samples. Melt pool depth and width measurements were made on optical micrographs. The dataset includes optical micrographs and melt pool width and depth measurements. These are supplemental experiments to the single-track laser scans for Additive Manufacturing Benchmark 2018 and 2022 challenges (https://www.nist.gov/ambench/am-bench-data-and-challenge-problems-0). Some of the data is associated with publications (1) https://doi.org/10.1016/j.jmapro.2021.10.053 and (2) https://doi.org/10.1007/s40192-022-00289-w.

Users are strongly encouraged to first review the “Master_TrackList_Measuremetns.xlsx” file for description of each image file.

Information on the directory structure and file formats are provided in the
README.txt file.


--------------
Data Use Notes
--------------

This data is publicly available according to the NIST statements of
copyright, fair use and licensing; see
https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software

You may cite the use of this data as follows:
Weaver, Jordan S., Deisenroth, David, Mekhontsev, Sergey, Heigel, Jarred, Lane, Brandon. (2023), Single-track laser scan cross-sectional micrographs on IN625 and IN718 bare plates with melt pool depth and width measurements, Version 1.0.0,
National Institute of Standards and Technology,
https://doi.org/10.18434/mds2-2716 (Accessed: [give download date])


--------------
Disclaimer
--------------

This data/work was created by employees of the National Institute of Standards and Technology (NIST), an agency of the Federal Government. Pursuant to title 17 United States Code Section 105, works of NIST employees are not subject to copyright protection in the United States.  This data/work may be subject to foreign copyright.
The data/work is provided by NIST as a public service and is expressly provided “AS IS.” NIST MAKES NO WARRANTY OF ANY KIND, EXPRESS, IMPLIED OR STATUTORY, INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTY OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT AND DATA ACCURACY. NIST does not warrant or make any representations regarding the use of the data or the results thereof, including but not limited to the correctness, accuracy, reliability or usefulness of the data. NIST SHALL NOT BE LIABLE AND YOU HEREBY RELEASE NIST FROM LIABILITY FOR ANY INDIRECT, CONSEQUENTIAL, SPECIAL, OR INCIDENTAL DAMAGES (INCLUDING DAMAGES FOR LOSS OF BUSINESS PROFITS, BUSINESS INTERRUPTION, LOSS OF BUSINESS INFORMATION, AND THE LIKE), WHETHER ARISING IN TORT, CONTRACT, OR OTHERWISE, ARISING FROM OR RELATING TO THE DATA (OR THE USE OF OR INABILITY TO USE THIS DATA), EVEN IF NIST HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.

To the extent that NIST may hold copyright in countries other than the United States, you are hereby granted the non-exclusive irrevocable and unconditional right to print, publish, prepare derivative works and distribute the NIST data, in any medium, or authorize others to do so on your behalf, on a royalty-free basis throughout the world.

You may improve, modify, and create derivative works of the data or any portion of the data, and you may copy and distribute such modifications or works. Modified works should carry a notice stating that you changed the data and should note the date and nature of any such change. Please explicitly acknowledge the National Institute of Standards and Technology as the source of the data:  Data citation recommendations are provided at https://www.nist.gov/open/license.
Permission to use this data is contingent upon your acceptance of the terms of this agreement and upon your providing appropriate acknowledgments of NIST’s creation of the data/work.

Certain commercial equipment, instruments, or materials are identified in this paper in order to specify the experimental procedure adequately.  Such identification is not intended to imply recommendation or endorsement by NIST, nor is it intended to imply that the materials or equipment identified are necessarily the best available for the purpose.


---------------
Version History
---------------

1.0.0 (this version)
  initial release


--------------------------
Methodological Information
--------------------------

  
 Machine settings:  
Three LPBF machines with Yb-fiber lasers were used to create laser tracks. The laser spot diameters were estimated on the two commercial machines (EOS M270 and EOS M290), and the spot diameter was measured for the Additive Manufacturing Metrology Testbed (AMMT). The laser power and scan speed are machine settings.

 Sample preparation:
Bare plates (25.4 mm x 25.4 mm x 3.175 mm) were either ground with 320 grit SiC paper or in the as-milled condition. Cross-sections were perpendicular to the laser scan direction and mostly taken in the center of tracks and always away from the transient start and end of the track. Samples were metallographically prepared and etched with Aqua Regia to reveal the melt pool boundary. More information is provided in https://doi.org/10.1016/j.jmapro.2021.10.053.

 Microscopy:
Optical micrographs were taken on various microscopes at various magnifications with bright field or dark field imaging. The pixel scaling is listed for each measurement in the “Master_TrackList_Measuremetns.xlsx” file.

 Measurement definitions:
The melt pool depth and width were measured with a bounding box as the deepest and widest dimensions, respectively. The top of the bounding box is aligned with the plate surface. Material above this line (i.e., humping or bead up) is neglected. The widest part of the melt pool does not necessarily have to occur at the plate surface. "Height" and "Width" annotations on micrographs correspond to the largest and shortest dimensions of the bounding box. These may be the depth and width or vice versa, depending on the aspect ratio of the melt pool. Please refer to the table of measurements for melt pool depth and width values. The expanded uncertainty (k = 2) of the mean width and depth was calculated following the work by Lane et al. 2020 (https://doi.org/10.1007/s40192-020-00169-1). This combines uncertainty components from user selection, optical resolution, width or depth variability along the track, and the standard uncertainty of the mean from repeated measurements. The variability in width and depth was estimated at 2 % and 5 %, respectively.

   
 
-------------
Data Manifest
-------------

2857_README.txt : This readme file.


Master_TrackList_Measurements.xls : Excel spreadsheet of measurement results in a table format. Individual measurements are listed on the sheet "Data" and a summary (averages and uncertainties) are listed on the sheet "Summary". The "Data" sheet lists the folder name and image name corresponding to each measurement.

/Top_Views/: 
	This directory contains top view images of the plates. The quality and state of the plate (before or after sectioning) varies.

/Micrographs/:
	This directory contains all of the micrographs organized by plate name. Each subfolder is a plate name with optical micrographs. Each track has two optical micrographs: one without the bounding box measurement and one with the bounding box measurement as an annotation on the image. Refer to the Master_TrackList_Measurements.xls file for measurement results.



