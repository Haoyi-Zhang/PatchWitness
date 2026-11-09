"""Watermark measurement, toolchain validation, and receiver semantics."""
from diagram_core import BLUE, RED, GRAY, HAIR, INK, WASH, WARM


def flow(d, xs, y, seq, *, side='below'):
    reach,_=d.units(10)
    for i,(x,(icon,label)) in enumerate(zip(xs,seq,strict=True)):
        d.node(x,y,icon,label,side=side,bold=i==len(xs)-1)
        if i:d.route((xs[i-1]+reach,y),(x-reach,y))


def arc(d, x1, x2, y1, y2, *, color=BLUE, dash=False):
    xm=(x1+x2)/2
    d.route((x1,y1),(xm,y1),(xm,y2),(x2,y2),color=color,dash=dash)


def outcome(d, x, y, icon, label, color=BLUE, size=9.3):
    d.icon(icon,x,y,color=color)
    left,_=d.units(12)
    d.t(x+left,y,label,align='left',color=color,bold=True,size=size)


def ledger(d,x,y,symbols, *, step=9, size=5, marked=(), color=BLUE):
    _,h=d.units(size)
    for i in range(len(symbols)):
        d.rect(x+i*step,y-h/2,step-2,h,fill=color if i in marked else WASH,edge=HAIR)


def mark_arch(d):
    d.node(45,34,'source','Original',side='above')
    d.node(45,70,'diff','Transformed')
    d.route((57,34),(103,34),(103,51),(134,51))
    d.route((57,70),(103,70),(103,51),(134,51),dash=True,color=GRAY)
    d.node(148,51,'policy','Fixed protocol')
    d.line((160,51),(199,51),(199,13),(199,87),color=GRAY,check=True)
    for y,ic,label in ((13,'run','Execution agreement'),(36,'diff','Source-form change'),
                      (64,'flag','Intervention survival'),(87,'grid','False-alarm bound')):
        d.route((199,y),(234,y))
        outcome(d,246,y,ic,label,size=9.1)


def channels(d):
    d.node(45,52,'source','Marked source')
    d.line((59,52),(110,52),(110,28),(110,75),color=GRAY,check=True)
    for y,icon,mid,end in ((28,'key','Identifier normalization','Lexical sites'),
                           (75,'tree','Structure normalization','Structural sites')):
        d.route((110,y),(196,y))
        d.node(211,y,icon,mid,side='above')
        d.route((226,y),(322,y))
        d.node(340,y,'diff',end)


def scopes(d):
    for y,left,seq,style in (
      (26,'Semantic audit',( ('source','Rendered programs'),('run','Run domain'),('compare','Compare outputs')),False),
      (75,'Dense matrix',( ('grid','Indexed states'),('flag','Apply attack'),('filter','Score detector')),True)):
        d.title(11,y,left,align='left',color=GRAY)
        for i,(x,(ic,tag)) in enumerate(zip((161,266,375),seq,strict=True)):
            d.node(x,y,ic,tag)
            if i:d.route((x-91,y),(x-14,y),dash=style)
    d.line((116,10),(116,93),color=HAIR)


def oracle_gap(d):
    d.t(12,22,'Declared domain',align='left',bold=True)
    d.t(12,60,'Nominal suite',align='left')
    d.t(12,84,'Reference vs mutant',align='left')
    xs=(163,200,237,274,311,359)
    for i,x in enumerate(xs):
        outside=x==359
        d.knot(x,45,color=RED if outside else BLUE,solid=outside)
        d.line((x,49),(x,73),dash=outside,color=RED if outside else HAIR)
        if not outside:d.knot(x,62,solid=True)
        d.icon('reject' if outside else 'check',x,83,color=RED if outside else BLUE,scale=.63)
    d.t(359,20,'Year 1200',color=RED,bold=True)
    d.span(151,329,55)


def motivating(d):
    d.title(26,15,'Extractor reads',align='left')
    d.title(220,15,'Payload')
    d.title(337,15,'Artifact binding')
    d.line((22,26),(393,26))
    for y,title,icon,bound in ((43,'Declared artifact','binary',True),(73,'Undeclared sidecar','keydoc',False)):
        outcome(d,34,y,icon,title,BLUE)
        d.t(220,y,'p',size=10.6,style='italic')
        d.icon('check' if bound else 'reject',292,y,color=BLUE if bound else RED)
        d.t(307,y,'Bound' if bound else 'Not bound',align='left',color=INK if bound else RED)


def trace_model(d):
    xs=(111,180,247,311,377)
    for x,(icon,title,record) in zip(xs,(
        ('key','Embed','Payload + key'),('chip','Compile','Build flags'),
        ('diff','Transform','Intervention'),('run','Execute','Output + exit'),
        ('filter','Extract','Artifact view')),strict=True):
        d.icon(icon,x,13)
        d.title(x,28,title)
        d.line((x,33),(x,77),color=HAIR)
        d.t(x,89,record,size=8.8)
    for y,name,dash in ((46,'Source',False),(66,'Follow-up',True)):
        d.t(8,y,name,align='left',bold=not dash)
        for i,x in enumerate(xs):
            d.knot(x,y,solid=not dash)
            if i:d.route((xs[i-1]+7,y),(x-7,y),dash=dash)


def admission(d):
    d.node(48,49,'policy','Required facts')
    d.route((62,49),(141,49))
    d.node(158,49,'filter','Admission',side='above')
    d.route((172,49),(220,49),(220,24),(263,24))
    d.route((220,49),(220,74),(263,74),color=RED,dash=True)
    d.t(245,13,'All hold',color=BLUE)
    d.t(243,92,'False / unavailable',color=RED)
    outcome(d,282,24,'compare','Evaluate predicate')
    outcome(d,282,74,'reject','Inadmissible',RED)


def architecture(d):
    d.node(44,47,'policy','Relation')
    d.line((58,47),(93,47),(93,27),(93,73),color=GRAY,check=True)
    for y,tag,dash in ((27,'Source trace',False),(73,'Follow-up trace',True)):
        d.route((93,y),(167,y),dash=dash)
        d.node(182,y,'trace',tag)
        d.route((198,y),(241,y),(241,48),(262,48),dash=dash)
    d.node(278,48,'keydoc','Typed record',side='above')
    d.route((293,48),(348,48))
    d.node(363,48,'compare','Contract verdict')


def carrier_fields(d):
    groups=((23,132,'Header',('Magic','Version'),'source'),(145,272,'Binding',('Key tag','Length'),'key'),
            (285,399,'Body',('Payload','Checksum'),'binary'))
    for a,b,title,fields,ic in groups:
        d.span(a,b,43,color=BLUE)
        x=(a+b)/2
        d.icon(ic,a+9,20,scale=.65)
        d.title(x+5,19,title)
        d.line((a,55),(b,55),color=GRAY)
        for xx in (a,x,b):
            d.line((xx,55),(xx,83),color=HAIR)
        d.t((a+x)/2,72,fields[0],size=8.7)
        d.t((b+x)/2,72,fields[1],size=8.7)


def removal(d):
    for x,ic,label in ((42,'binary','Admitted source'),(161,'diff','Removal observed?'),
                       (282,'filter','Extract again')):
        d.node(x,23,ic,label)
    d.route((55,23),(145,23));d.route((175,23),(267,23))
    d.route((161,46),(161,64),(76,64),(76,74),color=RED,dash=True)
    d.route((282,46),(282,63),(216,63),(216,74),color=RED)
    d.route((282,63),(371,63),(371,74))
    d.t(76,85,'No intervention',color=RED,bold=True)
    d.t(216,85,'Payload returned',color=RED,bold=True)
    d.t(371,85,'Absence rejection',color=BLUE,bold=True)


def design(d):
    d.title(73,12,'Fault units')
    for i,(ic,label) in enumerate((('source','18 subjects'),('binary','3 carriers'),('flag','24 mechanisms'))):
        outcome(d,24,31+i*16,ic,label,BLUE,9.2)
    d.line((19,74),(130,74),color=GRAY)
    d.t(73,85,'1,296 combinations',color=BLUE,bold=True)
    for x,ic,head in ((272,'source','Subject'),(335,'binary','Carrier'),(389,'flag','Mechanism')):
        d.icon(ic,x,15,scale=.78)
        d.title(x,25,head,size=8.6)
    for y,tag,fields in ((43,'Subject replay',('Change','Fixed','Fixed')),
            (63,'Carrier holdout',('','Omit one','')),
            (83,'Mechanism holdout',('','','Omit one'))):
        d.title(147,y,tag,align='left',size=8.9)
        for x,s in zip((272,335,389),fields,strict=True):
            if s:d.t(x,y,s,size=8.6,color=RED if s=='Omit one' else (BLUE if s=='Change' else GRAY))


def integrity(d):
    d.node(42,50,'rows','9 cases')
    d.line((56,50),(104,50),(104,22),(104,78),color=GRAY,check=True)
    for y,name,total in ((22,'Retained gate',9),(78,'Checksum-local gate',3)):
        d.route((104,y),(146,y))
        d.t(157,y,name,align='left',bold=True)
        ledger(d,276,y,range(9),step=8,marked=range(total))
        d.t(356,y,f'{total} admitted',align='left',color=BLUE)


def snapshot(d):
    d.route((45,59),(100,59),color=GRAY)
    d.route((124,59),(390,59),color=GRAY)
    d.icon('binary',34,59)
    d.icon('lock',112,59)
    d.knot(196,59,solid=True)
    d.knot(365,59,solid=True)
    d.t(277,78,'Extract',bold=True)
    for x,t in zip((34,112,196,365),('Capture S','Freeze F','Before read','After read'),strict=True):
        d.t(x,77,t)
    d.line((112,49),(112,23),(365,23),color=GRAY,dash=True,check=True)
    d.title(278,11,'Frozen view F')
    for x in (196,365):
        d.route((x,23),(x,52),color=BLUE,dash=True)
        d.t(x+17,37,'=',color=GRAY)


def checking_boundary(d):
    outcome(d,26,27,'diff','Candidate packet',RED)
    outcome(d,26,72,'source','Receiver request')
    d.route((129,27),(170,27),(170,44),(196,44),color=RED,dash=True)
    d.route((129,72),(170,72),(170,53),(196,53))
    d.node(214,49,'tree','Reconstruct + check')
    d.line((228,49),(279,49),(279,24),(279,72),color=GRAY,check=True)
    d.route((279,24),(301,24));d.route((279,72),(301,72),dash=True)
    outcome(d,313,24,'grid','All inputs')
    outcome(d,313,72,'point','One violation')


def definedness(d):
    d.title(58,50,'Q(x) = x / 0',size=10.5)
    d.line((108,50),(155,50),(155,23),(155,76),color=GRAY,check=True)
    for y,ic,color,eq,lbl in ((23,'run',BLUE,'Value = 0','Total circuit'),
                                (76,'reject',RED,'Defined = false','Source rule')):
        d.route((155,y),(197,y),color=color)
        d.icon(ic,211,y,color=color)
        d.title(228,y,eq,align='left',color=color)
        d.t(334,y,lbl,align='left')


def replay_control(d):
    d.node(44,50,'source','Same request')
    d.line((59,50),(96,50),(96,25),(96,75),color=GRAY,check=True)
    d.route((96,25),(135,25));d.route((96,75),(235,75),dash=True)
    d.node(149,25,'rows','Producer rows')
    d.route((164,25),(234,25))
    d.node(250,25,'filter','Admit and check')
    d.node(250,75,'run','Direct evaluation')
    d.route((265,25),(318,25),(318,50),(354,50))
    d.route((265,75),(318,75),(318,50),(354,50),dash=True)
    d.node(371,50,'flag','Diagnostic',bold=True)


def cache(d):
    d.node(39,49,'key','Term + inputs')
    d.route((53,49),(114,49))
    d.node(130,49,'store','Receiver cache')
    d.line((145,49),(173,49),(173,23),(173,74),color=GRAY,check=True)
    d.route((173,23),(228,23));d.route((173,74),(228,74),dash=True)
    d.t(199,11,'Hit',color=BLUE);d.t(199,88,'Miss',color=GRAY)
    d.node(243,23,'keydoc','Lookup value')
    d.node(243,74,'run','Evaluate cell')
    d.route((258,23),(313,23),(313,49),(354,49))
    d.route((258,74),(313,74),(313,49),(354,49),dash=True)
    d.node(370,49,'compare','Compare cell',bold=True)


def point_refutation(d):
    d.title(53,26,'Claimed point')
    d.icon('point',53,61)
    d.route((68,61),(148,61))
    d.title(211,26,'Receiver evaluation')
    d.span(155,266,51,color=GRAY)
    d.t(211,73,'Rebuilt circuit + trace')
    d.route((270,61),(326,61))
    d.title(365,26,'Obligation')
    d.icon('flag',365,61)


FIGURES={
 'MarkValidity_TOSEM':{'architecture':mark_arch,'channel-interventions':channels,
                       'execution-scopes':scopes,'oracle-gap':oracle_gap},
 'ToolchainMark_TOSEM':{'motivating-counterexample':motivating,'trace-model':trace_model,
                       'admission-vs-attribution':admission,'architecture':architecture,
                       'carrier-record-fields':carrier_fields,'removal-verdict-flow':removal,
                       'evaluation-design':design,'integrity-admission-controls':integrity,
                       'snapshot-coherence':snapshot},
 'RepairSeal_TOSEM':{'checking-boundary':checking_boundary,'definedness-rule-tree':definedness,
                     'trust-boundary':replay_control,'receiver-owned-cache':cache,
                     'one-point-refutation':point_refutation},
}
