// Four-channel controller enclosure. Hardware envelopes are assumptions except nominal 70x50 perfboard.
$fn=48;
part="assembly"; // bottom, lid, layout, assembly
wall=2.4; floor_t=2.4; lid_t=2.4; corner_r=3;
inner_x=146; inner_y=130; cavity_h=30;
// Positions are XY centers. Total height includes underside solder / headers.
board_sizes=[[30,65,14],[70,50,14],[30,50,12],[80,40,24],[35,28,15]];
board_positions=[[-54,20],[3,20],[56,20],[-25,-43],[49,-43]];
// 0 ESP32; 1 perfboard; 2 remote PCB; 3 existing battery holder; 4 optional power module space.
show_power_module=false;
support_h=4; support_w=4; support_inset=6;
tie_slot_x=3; tie_slot_y=5; tie_edge_gap=2;
screw_clearance=2.6; screw_pilot=2.0; boss_d=6; boss_offset=5; pilot_depth=12;
ear_projection=12; ear_width=16; ear_h=4; ear_hole=4.5; ear_y=-40;
// Cable notch on +Y wall, aligned with ESP area. USB extension, not a fitted socket opening.
usb_x=-54; usb_width=24; usb_depth=23;
exploded_gap=22; layout_gap=15; show_hardware=true;
// Optional lid access requires MEASURED coordinates. Disabled until measured.
access_holes=false;
button_centers=[[25,39],[25,26],[25,13],[25,0]];
led_centers=[[8,39],[8,26],[8,13],[8,0]];
button_access_d=10; led_access_d=6;
eps=.05;
outer_x=inner_x+2*wall; outer_y=inner_y+2*wall; bottom_h=floor_t+cavity_h;
module rounded_box(s,r){linear_extrude(s[2])offset(r=r)square([s[0]-2*r,s[1]-2*r],center=true);}
module screw_positions(){for(x=[-1,1],y=[-1,1])translate([x*(outer_x/2-boss_offset),y*(outer_y/2-boss_offset),0])children();}
module supports(){for(i=[0:3],side=[-1,1])translate([board_positions[i][0],board_positions[i][1]+side*(board_sizes[i][1]/2-support_inset),floor_t-eps])linear_extrude(support_h+eps)square([board_sizes[i][0],support_w],center=true);}
module tie_slots(){for(i=[0:3],side=[-1,1],end=[-1,1])translate([board_positions[i][0]+side*(board_sizes[i][0]/2+tie_edge_gap),board_positions[i][1]+end*(board_sizes[i][1]/2-support_inset),-eps])linear_extrude(floor_t+2*eps)square([tie_slot_x,tie_slot_y],center=true);}
module bottom_case(){difference(){union(){
 difference(){rounded_box([outer_x,outer_y,bottom_h],corner_r);translate([0,0,floor_t])rounded_box([inner_x,inner_y,bottom_h],max(.1,corner_r-wall));}
 screw_positions()cylinder(h=bottom_h,d=boss_d);
 supports();
 for(side=[-1,1])translate([side*(outer_x/2+ear_projection/2-wall/2),ear_y,0])rounded_box([ear_projection+wall,ear_width,ear_h],corner_r);
 }
 screw_positions()translate([0,0,bottom_h-pilot_depth])cylinder(h=pilot_depth+eps,d=screw_pilot);
 tie_slots();
 for(side=[-1,1])translate([side*(outer_x/2+ear_projection/2),ear_y,-eps])cylinder(h=ear_h+2*eps,d=ear_hole);
 translate([usb_x,outer_y/2,bottom_h-usb_depth/2+eps])cube([usb_width,wall*3,usb_depth+2*eps],center=true);
}}
module lid(){difference(){rounded_box([outer_x,outer_y,lid_t],corner_r);screw_positions()translate([0,0,-eps])cylinder(h=lid_t+2*eps,d=screw_clearance);
 if(access_holes){for(p=button_centers)translate([p[0],p[1],-eps])cylinder(h=lid_t+2*eps,d=button_access_d);for(p=led_centers)translate([p[0],p[1],-eps])cylinder(h=lid_t+2*eps,d=led_access_d);}
}}
module hardware(){for(i=[0:show_power_module?4:3])color(i==0?"DarkSlateGray":i==1?"DarkOrange":i==2?"SeaGreen":"SteelBlue",.65)translate([board_positions[i][0],board_positions[i][1],floor_t+support_h])linear_extrude(board_sizes[i][2])square([board_sizes[i][0],board_sizes[i][1]],center=true);}
assert(cavity_h>=support_h+max([for(s=board_sizes)s[2]])+2,"Increase cavity height");
assert(bottom_h-pilot_depth>floor_t);
echo(body=[outer_x,outer_y,bottom_h+lid_t]);
if(part=="bottom")bottom_case();else if(part=="lid")lid();else if(part=="layout"){bottom_case();translate([0,outer_y+layout_gap,0])lid();}else{bottom_case();if(show_hardware)hardware();translate([0,0,bottom_h+exploded_gap])color("LightSteelBlue",.5)lid();}
