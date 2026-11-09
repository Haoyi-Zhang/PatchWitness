"""Search contracts, Android provenance, replay, and patch evidence."""
from diagram_core import BLUE, RED, GRAY, HAIR, INK, WASH, WARM
from diagram_kim import flow, outcome, ledger


def search(d):
    for y,name in ((19,'Shard A'),(44,'Shard B'),(68,'Shard C')):
        d.t(9,y,name,align='left',size=8.8)
        ledger(d,59,y,range(5),step=10,marked=range({19:5,44:3,68:4}[y]))
        d.line((111,y),(145,y),color=BLUE,check=True)
    d.line((145,19),(145,68),color=BLUE,check=True)
    d.route((145,44),(175,44))
    d.node(189,44,'merge','Merge')
    d.route((203,44),(240,44),(240,19),(274,19))
    d.route((240,44),(240,45),(274,45),color=RED)
    outcome(d,287,19,'check','Exact top-k')
    outcome(d,287,45,'partial','Refill or partial',RED)
    d.route((145,68),(145,86),(272,86),dash=True,color=GRAY)
    d.route((240,45),(240,67),(254,67),(254,84),dash=True,color=GRAY)
    outcome(d,287,86,'compare','Independent replay')


def continuation(d):
    xs=(130,191,251,311,377)
    d.title(130,13,'Token cut');d.title(377,13,'Target cut')
    for y,l in ((37,'Writer'),(61,'Receipts'),(85,'Index')):
        d.t(10,y,l,align='left',bold=True)
    for x in (130,377):d.line((x,22),(x,91),dash=True,color=HAIR)
    for i,x in enumerate(xs):
        d.knot(x,37,solid=True)
        if i:
            a=xs[i-1]
            d.route((a+6,37),(x-6,37))
            d.span(a+4,x-4,52,color=BLUE)
            d.t((a+x)/2,67,f'r{i}',style='italic')
    d.route((130,85),(297,85),color=GRAY)
    d.knot(306,85,color=GRAY);d.t(343,85,'May lag',color=GRAY)


def running(d):
    xs={1:144,2:179,3:214,7:296,9:370}
    d.t(369,12,'Tail bound',bold=True)
    d.line((343,24),(343,94),color=GRAY,dash=True)
    for y,name,values in ((30,'Initial',(1,3,7)),(55,'After rewrite',(1,2,7)),(80,'After deletion',(7,))):
        d.t(11,y,name,align='left',bold=y==30)
        d.line((125,y),(321,y))
        for k in values:
            rx,ry=d.units(7.1)
            d.rect(xs[k]-rx,y-ry,2*rx,2*ry,fill=WASH,edge=BLUE,z=5)
            d.title(xs[k],y,str(k),color=BLUE)
        d.title(xs[9],y,'9')
    d.route((207,38),(186,47),color=RED,dash=True)


def target(d):
    d.node(36,35,'stream','Advance')
    d.route((50,35),(105,35))
    d.node(121,35,'checkgrid','Coverage',side='above')
    d.route((135,35),(207,35))
    d.node(223,35,'filter','Unseen tail',side='above')
    d.route((237,35),(311,35))
    outcome(d,326,35,'check','Exact top-k')
    d.route((121,49),(121,68),(91,68),(91,76),color=RED,dash=True)
    d.route((223,49),(223,68),(281,68),(281,76),color=RED)
    d.t(91,87,'Missing shard: partial',color=RED)
    d.t(281,87,'Blocking tail: refill, then recheck',color=RED)


def checker(d):
    d.title(52,16,'Prior token'); d.title(52,81,'Bound receipts')
    d.icon('key',109,22,scale=.80);d.icon('stream',109,73,scale=.80)
    d.route((123,22),(153,22),(153,49),(179,49))
    d.route((123,73),(153,73),(153,49),(179,49),dash=True)
    d.node(195,49,'run','Replay',side='above')
    d.route((208,49),(257,49))
    d.node(273,49,'keydoc','Next token',side='below')
    d.route((287,49),(345,49))
    d.node(361,49,'compare','Check result',side='above')


def retention(d):
    y=54
    d.t(95,15,'Eligible to prune',color=GRAY,bold=True)
    d.t(317,15,'Keep for replay',color=BLUE,bold=True)
    d.line((32,y),(192,y),color=HAIR,dash=True,weight=1.15)
    d.route((194,y),(390,y),weight=1.15)
    for x in (53,91,129,167):d.knot(x,y,color=GRAY)
    for x in (222,257,292,327,362):d.knot(x,y,solid=True)
    d.line((194,31),(194,66),color=GRAY,check=True)
    d.line((292,40),(292,65),color=GRAY,check=True)
    d.t(194,78,'Slowest cursor',bold=True)
    d.t(292,78,'Later cursor',color=GRAY)
    d.t(94,82,'Subject to repair window',color=GRAY,size=8.8)


def taxonomy(d):
    d.node(55,49,'apk','APK lineage')
    d.line((69,49),(114,49),(114,15),(114,83),color=GRAY,check=True)
    for y,icon,title,labels in (
      (15,'compare','Artifact comparison','L0 Identity  ·  L1 Composition  ·  L2 Resemblance'),
      (48,'trace','Production records','L3 Derivation  ·  L4 Process provenance'),
      (82,'lock','Policy and behavior','L5 Authorization  ·  L6 Behavioral assurance')):
        d.route((114,y),(145,y))
        d.icon(icon,159,y)
        d.t(178,y-3,title,align='left',bold=True)
        d.t(178,y+10,labels,align='left',size=9.1)


def histories(d):
    d.title(98,10,'Direct derivation')
    d.title(309,10,'Shared ancestor')
    d.node(45,54,'apk','APK A')
    d.node(149,54,'apk','APK B')
    d.route((59,54),(134,54));d.t(96,38,'Transform')
    d.node(313,34,'source','Predecessor',side='right')
    d.route((304,44),(265,53),(265,64))
    d.route((322,44),(362,53),(362,64))
    for x,l in ((265,'APK A'),(362,'APK B')):
        d.node(x,75,'apk',l)


def shared(d):
    d.node(57,32,'apk','APK A',side='above')
    d.node(361,32,'apk','APK B',side='above')
    d.node(210,32,'shared','Shared library')
    d.line((72,32),(194,32),color=GRAY,dash=True,check=True)
    d.line((225,32),(346,32),color=GRAY,dash=True,check=True)
    for x,ic,s in ((57,'cert','Authenticated release'),(361,'run','Observed behavior')):
        d.route((x,44),(x,65))
        d.node(x,76,ic,s)


def library(d):
    d.node(50,52,'shared','Family match')
    d.route((64,52),(126,52))
    d.node(142,52,'filter','Distinctive traits',side='above')
    d.line((157,52),(196,52),(196,26),(196,77),color=GRAY,check=True)
    for y,name,lab,count in ((26,'Observed','Narrow candidates',2),(77,'Missing','Keep candidate set',5)):
        d.route((196,y),(253,y),dash=y==77)
        d.t(223,y-12,name,color=GRAY)
        for k in range(count):d.icon('shared',266+k*9,y,scale=.48)
        d.t(369,y,lab,align='center',bold=True)


def lifecycle(d):
    xs=(37,107,177,247,317,387)
    for x,ic,stage,doc in zip(xs,('source','shared','chip','lock','apk','run'),
                             ('Source','Resolve','Build','Approve','Distribute','Execute'),
                             ('History','SBOM','Attestation','Delegation','Transparency','Observation'),strict=True):
        if stage in ('Build','Approve','Distribute'):
            d.icon(ic,x,33)
        d.title(x,15,stage)
        d.knot(x,52,solid=True)
        d.line((x,56),(x,76),color=GRAY,dash=True)
        d.t(x,85,doc,size=8.8)
    for a,b in zip(xs,xs[1:]):d.route((a+6,52),(b-6,52))


def generation(d):
    xs=(43,150,260,373)
    for x,ic,lab in zip(xs,('source','trace','diff','apk'),
                       ('Parent revision','Generation record','Accepted patch','Built APK'),strict=True):
        d.node(x,52,ic,lab,side='above' if x in (43,260) else 'below')
    for a,b in zip(xs,xs[1:]):d.route((a+12,52),(b-13,52),dash=a==150)
    d.t(205,29,'Approval',size=8.8,color=GRAY)


def assurance(d):
    d.node(53,23,'cert','Release evidence')
    d.node(53,70,'run','Property Q')
    d.route((67,23),(126,23),(126,44),(162,44))
    d.route((67,70),(126,70),(126,53),(162,53))
    d.node(179,49,'apk','Same APK',side='above',bold=True)
    d.route((195,49),(288,49))
    outcome(d,306,49,'check','Joint claim')
    d.node(327,82,'shared','Component comparison')
    d.route((313,82),(246,82),(246,58),(211,58),color=GRAY,dash=True)


def drift_arch(d):
    d.node(37,32,'policy','Old frame',side='above')
    d.node(37,73,'diff','Final frame')
    for y in (32,73):
        d.route((51,y),(94,y),(94,53),(125,53))
    d.node(139,53,'tree','Delta')
    d.route((153,53),(220,53))
    d.node(236,53,'filter','Checker')
    d.node(175,16,'cert','Candidate',side='right')
    d.route((175,26),(175,36),(236,36),(236,43),dash=True,color=GRAY)
    d.line((250,53),(276,53),(276,21),(276,82),color=GRAY,check=True)
    for y,ic,name in ((21,'point','Identify core'),(53,'check','Verify candidate'),(82,'compare','Compare views')):
        d.route((276,y),(300,y))
        outcome(d,313,y,ic,name)


def final_reads(d):
    xs=(151,255,362)
    d.t(10,48,'Old',align='left');d.t(10,72,'Final',align='left',bold=True)
    for i,(x,label) in enumerate(zip(xs,('Deleted\nrule','New\nmapping','Unread\nedit'),strict=True)):
        d.title(x,19,label,size=8.8)
        d.line((x,34),(x,86),color=HAIR)
        d.knot(x,48,solid=i==0)
        d.knot(x,72,solid=i!=2)
        d.icon('check' if i!=2 else 'partial',x,90,color=BLUE if i!=2 else GRAY,scale=.63)


def interacting(d):
    entries=((110,23,'No edit','T   F   F'),(318,23,'Only edit 2','T   T   F'),
             (110,73,'Only edit 3','U   F   F'),(318,73,'Edits 2 and 3','U   T   U'))
    for i,(x,y,title,vals) in enumerate(entries):
        d.title(x,y-9,title,size=9.2,color=BLUE if i==3 else INK)
        d.t(x,y+3,'p    q    rule',size=8.6,color=GRAY)
        d.title(x,y+14,vals,size=9.6,color=BLUE if i==3 else INK)
    for y in (24,74):d.route((174,y),(244,y),dash=y==24)
    for x in (109,316):d.route((x,43),(x,57),dash=x==109)
    d.icon('check',377,89)
    d.t(115,94,'T true; F false; U unknown',size=8.6,color=GRAY)


def minima(d):
    d.title(114,11,'Truth only')
    d.title(312,11,'Complete evidence')
    d.line((218,20),(218,90),color=HAIR,dash=True)
    d.t(110,34,'{u, v}',bold=True)
    d.route((110,44),(68,61),(68,66))
    d.route((110,44),(153,61),(153,66))
    d.t(68,79,'{u}',bold=True,color=BLUE)
    d.t(153,79,'{v}',bold=True,color=BLUE)
    d.title(312,42,'{u, v}',size=10.4)
    d.span(274,349,57,color=GRAY)
    d.t(312,73,'Both required')


def witness(d):
    d.title(68,29,'Case C01')
    d.icon('point',35,54)
    d.t(68,54,'x = 3',size=10.2)
    d.route((97,54),(135,54),(135,89),(393,89),(393,82),color=GRAY)
    d.t(168,13,'Declared domain',align='left',bold=True)
    d.rect(378,43,32,21,fill=WARM,edge=WARM);d.rect(378,64,32,21,fill=WASH,edge=WASH)
    for y,name,v in ((33,'Input',('0','1','2','3')),(54,'Old',('1','2','3','fault')),(75,'New',('1','2','3','3'))):
        d.t(168,y,name,align='left',bold=y==33)
        for x,s in zip((224,279,334,393),v,strict=True):
            d.t(x,y,s,bold=y==33 or x==393,color=RED if s=='fault' else INK)


def replay(d):
    d.node(43,64,'source','Expected IR')
    d.node(149,26,'cert','Producer certificate',side='above',color=GRAY)
    d.route((58,64),(202,64))
    d.route((85,64),(85,26),(133,26),color=GRAY,dash=True)
    d.route((163,26),(219,26),(219,51),color=GRAY,dash=True)
    d.node(219,64,'run','Receiver replay')
    d.route((234,64),(316,64))
    d.node(332,64,'point','One input')
    d.t(355,38,'Fault → defined',color=BLUE,bold=True)


def guard(d):
    d.title(84,13,'Dimension input')
    d.line((34,49),(388,49),color=GRAY,weight=.9)
    for x,s in ((130,'−1'),(210,'0')):
        d.knot(x,49,color=RED if x==210 else BLUE,solid=x in (130,210))
        d.t(x,67,s,color=RED if x==210 else INK)
    d.t(130,88,'Source trigger',bold=True,color=BLUE)
    d.route((210,46),(210,31),(277,31),color=RED,dash=True)
    d.t(284,31,'Expression test only',align='left',color=RED,bold=True)


def pipeline(d):
    d.t(13,16,'Prediction process',align='left',bold=True)
    d.t(13,84,'Scoring process',align='left',bold=True)
    d.line((125,50),(410,50),color=GRAY,dash=True)
    d.t(52,37,'Cases + rule',align='left')
    d.route((126,37),(198,37))
    d.node(214,37,'lock','Freeze predictions',side='above')
    d.route((214,49),(214,70),(275,70))
    d.node(291,70,'compare','Score',side='below')
    d.node(136,79,'keydoc','Separate labels',side='above')
    d.route((151,79),(241,79),(241,70),(269,70),dash=True,color=GRAY)
    d.route((306,70),(341,70))
    d.title(371,70,'Metrics')


FIGURES={
 'CodeSearch_TOSEM':{'protocol':search,'continuation-cut':continuation,'running-example':running,
                     'target-cut-certification':target,'checker-owned-state':checker,'feed-retention-boundary':retention},
 'AndroidEvidence_CSUR':{'claim-ladder':taxonomy,'lineage-histories':histories,'worked-claim':shared,
                         'library-attribution':library,'mobile-lifecycle':lifecycle,
                         'generation-release-binding':generation,'assurance-pattern':assurance},
 'DriftExplain_TSE':{'architecture':drift_arch,'final-read-support':final_reads,
                     'interacting-delta':interacting,'two-minima':minima},
 'PatchWitness_TOSEM':{'evidence-ladder':witness,'trust-boundary':replay,'guard-context-branches':guard,
                       'study-pipeline':pipeline},
}
