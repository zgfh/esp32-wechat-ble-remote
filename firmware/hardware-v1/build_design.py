from pathlib import Path
from html import escape
import json
P=Path(__file__).parent
# Core shell adapted from repository enclosure template; geometry in mm.
scad='''// Four-channel controller enclosure. Hardware envelopes are assumptions except nominal 70x50 perfboard.
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
'''
(P/'controller-case.scad').write_text(scad)
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1400" viewBox="0 0 1400 1400"><rect width="1400" height="1400" fill="#f8fafc"/><style>text{font-family:PingFang SC,Arial,sans-serif;fill:#172b4d} .wire{fill:none;stroke:#334155;stroke-width:3}</style>']
def text(x,y,t,size=21):svg.append(f'<text x="{x}" y="{y}" font-size="{size}">{escape(t)}</text>')
def line(points):svg.append(f'<polyline points="{points}" class="wire"/>')
def box(x,y,w,h,t):svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="white" stroke="#64748b" stroke-width="2"/>');text(x+10,y+h/2+7,t,20)
text(45,50,'四路 PC817 永久接线：每一路照此重复',30)
text(45,87,'电气原理图，不是洞洞板孔位图；按脚号焊接，背面视角左右相反。')
svg.append('<path d="M790 115 V640" stroke="#e11d48" stroke-width="3" stroke-dasharray="10 7"/>')
text(70,140,'ESP32 侧：共用 ESP32 GND',24);text(865,140,'遥控器侧：每路独立触点对',24)
text(45,245,'GPIO');line('110,240 175,240 175,190 245,190');box(245,170,115,40,'330 Ω');line('360,190 525,190');box(525,160,220,180,'PC817');text(535,198,'1 → 内部红外 LED',18);text(535,292,'2 → ESP32 GND',18)
line('175,240 175,370 245,370');box(245,350,115,40,'1 kΩ');line('360,370 400,370');box(400,350,210,40,'指示 LED：＋ → −');line('610,370 665,370 665,420 220,420');text(225,450,'GND（输入侧公共线）',20)
line('525,290 500,290 500,345 700,345 700,420 665,420');line('175,240 130,240 130,490 245,490');box(245,470,115,40,'10 kΩ');line('360,490 480,490 480,420');text(45,545,'10 kΩ 下拉接在 GPIO 与 GND 之间。',20)
line('745,190 940,190 1190,190');text(755,180,'4 / C',18);text(1195,196,'触点 A',20)
line('745,290 940,290 1190,290');text(755,325,'3 / E',18);text(1195,298,'触点 B',20)
line('940,190 940,220');line('940,260 940,290');line('940,220 967,251');text(990,242,'常开按钮',21)
text(845,380,'A：测得相对正端 → 4 脚',21);text(845,415,'B：测得相对负端 → 3 脚',21)
text(845,475,'按钮直接跨 A、B，绕过软件。',21)
text(845,515,'不接 ESP32 的 3V3 / GND。',21)
text(845,555,'四路 A/B 不自行合并成公共线。',21)
text(45,602,'LED 只表示 GPIO 输入状态，不能证明光耦输出或车辆状态。',22)
box(45,650,1310,270,'')
text(70,690,'通道（按照片从上到下）     普通 ESP32       ESP32-S3       当前软件',22)
for y,t in [(730,'1 红色 / 锁车                         GPIO26             GPIO4             已有'),(770,'2 绿色 / 解锁                         GPIO27             GPIO5             已有'),(810,'3 黄色 / 第三功能                  GPIO25             GPIO6             固件命名 start，触点需确认'),(850,'4 蓝色 / 预留                         暂不接 GPIO      暂不接 GPIO      尚未实现')]:text(70,y,t,20)
text(70,891,'供电：ESP32 用 USB；遥控器保留原供电。双节电池座接法等待型号、电压及极性确认。',20)
text(45,966,'先断电焊接。PC817 按厂家 1 脚标记识别；四脚按钮先用通断档找出按下才接通的一对。',20)
svg.append('</svg>');(P/'wiring.svg').write_text('\n'.join(svg))
channels=[]
for n,g,sg in [(1,26,4),(2,27,5),(3,25,6),(4,None,None)]:
 channels.append(dict(channel=n,esp32_gpio=g,s3_gpio=sg,nets={f'IN{n}':[f'Ropto{n}.1',f'Rled{n}.1',f'Rdown{n}.1'],f'OPTO_A{n}':[f'Ropto{n}.2',f'U{n}.1'],f'LED_A{n}':[f'Rled{n}.2',f'LED{n}.A'],'ESP_GND':[f'U{n}.2',f'LED{n}.K',f'Rdown{n}.2'],f'REMOTE_A{n}':[f'U{n}.4',f'SW{n}.A',f'J{n}.A'],f'REMOTE_B{n}':[f'U{n}.3',f'SW{n}.B',f'J{n}.B']}))
(P/'netlist.json').write_text(json.dumps(channels,ensure_ascii=False,indent=2)+'\n')
# Verify all component terminals occur exactly once, output nets never join ESP ground.
for c in channels:
 terminals=[t for net in c['nets'].values() for t in net]
 assert len(terminals)==len(set(terminals))==16
 for name,net in c['nets'].items():
  if name.startswith('REMOTE_'):assert all(t.startswith(('U','SW','J')) for t in net)
import xml.etree.ElementTree as ET
ET.parse(P/'wiring.svg')
print('Generated SCAD, SVG and four-channel netlist; terminal uniqueness and SVG parsing passed.')
