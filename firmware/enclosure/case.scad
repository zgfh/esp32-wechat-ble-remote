/* Adapted from openscad-enclosure/assets/esp32_case_template.scad.
   DRAFT: all hardware envelopes below are assumptions, in mm. */
$fn=48;
part="assembly"; // bottom, lid, layout, assembly
// Measured hardware envelopes INCLUDING headers, plugs and underside joints.
esp_size=[65,30,18];
opto_size=[40,30,15];
remote_size=[65,38,20];
include_remote=true;
clearance=3;
module_gap=8;
wall=2.4;
floor_thickness=2.4;
lid_thickness=2.4;
corner_radius=3;
headroom=5;
support_height=4;
support_width=5;
support_edge_inset=7;
// Cable ties wrap around module + support rails through bottom slots.
tie_slot_width=3;
tie_slot_length=5;
tie_edge_margin=3;
// Four M2.5 self-tapping screws. Pilot must be tuned on a printed sample.
screw_clearance=2.6;
screw_pilot=2.0;
boss_diameter=6;
boss_offset=5;
pilot_depth=12;
// Broad cable exit, open at top for easy cable installation. Not watertight.
cable_opening_width=18;
cable_opening_depth=10;
cable_opening_y=0;
// External mounting tabs, M4 screw holes.
ear_width=14;
ear_projection=12;
ear_thickness=4;
ear_hole=4.5;
exploded_gap=18;
layout_gap=15;
show_hardware=true;

sizes=include_remote?[esp_size,opto_size,remote_size]:[esp_size,opto_size];
inner_length=max([for(s=sizes)s[0]])+2*clearance+2*boss_diameter;
inner_width=esp_size[1]+opto_size[1]+(include_remote?remote_size[1]:0)+(len(sizes)-1)*module_gap+2*clearance+2*boss_diameter;
outer_length=inner_length+2*wall;
outer_width=inner_width+2*wall;
bottom_height=floor_thickness+support_height+max([for(s=sizes)s[2]])+headroom;
function sum_before(i)=i==0?0:sizes[i-1][1]+module_gap+sum_before(i-1);
function cy(i)=-inner_width/2+clearance+boss_diameter+sum_before(i)+sizes[i][1]/2;
module rounded_box(size,r){linear_extrude(size[2])offset(r=r)square([size[0]-2*r,size[1]-2*r],center=true);}
module screws(){for(x=[-1,1],y=[-1,1])translate([x*(outer_length/2-boss_offset),y*(outer_width/2-boss_offset),0])children();}
module bottom_case(){difference(){union(){
 difference(){rounded_box([outer_length,outer_width,bottom_height],corner_radius);translate([0,0,floor_thickness])rounded_box([inner_length,inner_width,bottom_height],max(.1,corner_radius-wall));}
 screws()cylinder(h=bottom_height,d=boss_diameter);
 for(i=[0:len(sizes)-1],side=[-1,1])translate([side*(sizes[i][0]/2-support_edge_inset),cy(i),floor_thickness+support_height/2-.05])cube([support_width,sizes[i][1],support_height+.1],center=true);
 for(side=[-1,1])translate([side*(outer_length/2+ear_projection/2-wall/2),0,0])rounded_box([ear_projection+wall,ear_width,ear_thickness],corner_radius);
 }
 screws()translate([0,0,max(floor_thickness,bottom_height-pilot_depth)])cylinder(h=pilot_depth+1,d=screw_pilot);
 for(side=[-1,1])translate([side*(outer_length/2+ear_projection/2),0,-1])cylinder(h=ear_thickness+2,d=ear_hole);
 translate([-outer_length/2,cable_opening_y,bottom_height-cable_opening_depth/2+.5])cube([wall*3,cable_opening_width,cable_opening_depth+1],center=true);
 for(i=[0:len(sizes)-1],xside=[-1,1],yside=[-1,1])translate([xside*(sizes[i][0]/2-support_edge_inset),cy(i)+yside*(sizes[i][1]/2+tie_edge_margin),floor_thickness/2])cube([tie_slot_length,tie_slot_width,floor_thickness+2],center=true);
}}
// Flat lid: no unverified snap fits or lip/boss intersections.
module lid(){difference(){rounded_box([outer_length,outer_width,lid_thickness],corner_radius);screws()translate([0,0,-1])cylinder(h=lid_thickness+2,d=screw_clearance);}}
module hardware(){for(i=[0:len(sizes)-1])color(i==0?"SeaGreen":i==1?"orange":"DimGray",.5)translate([0,cy(i),floor_thickness+support_height+sizes[i][2]/2])cube(sizes[i],center=true);}
assert(screw_pilot<screw_clearance);
assert(module_gap>2*tie_edge_margin+tie_slot_width/2);
echo(outer_dimensions=[outer_length,outer_width,bottom_height+lid_thickness]);
if(part=="bottom")bottom_case();
else if(part=="lid")lid();
else if(part=="layout"){bottom_case();translate([0,outer_width+layout_gap,0])lid();}
else{bottom_case();if(show_hardware)hardware();translate([0,0,bottom_height+exploded_gap])color("LightSteelBlue")lid();}
