import './about-provenance.css';

type CardProps = {
  x: number;
  y: number;
  width: number;
  height: number;
  title: string;
  lines: string[];
  fill: string;
  stroke: string;
  titleColor?: string;
};

function DiagramCard({ x, y, width, height, title, lines, fill, stroke, titleColor = '#f5e4d0' }: CardProps) {
  return <g>
    <rect x={x} y={y} width={width} height={height} rx="10" fill={fill} stroke={stroke} strokeWidth="1.6"/>
    <text x={x + 12} y={y + 24} fill={titleColor} fontSize="15" fontWeight="650">{title}</text>
    <text x={x + 12} y={y + 42} fill="#c5d1da" fontSize="11.5">
      {lines.map((line, index) => <tspan key={index} x={x + 12} dy={index === 0 ? 0 : 15}>{line}</tspan>)}
    </text>
  </g>;
}

function FlowArrow({ d, tone = 'blue', dashed = false, prefix = 'about-provenance' }: { d: string; prefix?: string; tone?: 'blue' | 'green' | 'gold' | 'violet' | 'coral'; dashed?: boolean }) {
  const color = { blue: '#78bbee', green: '#85cfa7', gold: 'var(--sigma-copper-foreground)', violet: '#b59ff5', coral: '#f0a098' }[tone];
  return <path d={d} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" strokeDasharray={dashed ? '5 5' : undefined} markerEnd={`url(#${prefix}-arrow-${tone})`}/>;
}

/** Illustrative provenance relationships. This is a product vision, not a live graph viewer. */
export default function AboutProvenanceVision() {
  return <section className="about-provenance" aria-label="Vision for Investigation Provenance">
    <p><strong>Beyond a linear LLM conversation.</strong> A conventional chat moves from prompt to response to another prompt and response. Its transcript preserves the exchange, but the relationships among evidence, competing ideas, challenges, and revisions can remain buried in the text. An investigation can be more than a sequence of messages: it can branch, revisit earlier findings, reconcile contradictions, and bring together scientific papers, AI agents, and human judgment.</p>
    <div className="about-provenance-comparison" aria-label="Linear chat versus provenance-led investigation">
      <div>
        <strong>Conventional LLM chat</strong>
        <span>Prompt → Response → Prompt → Response</span>
        <small>A chronological conversation</small>
      </div>
      <div>
        <strong>SIGMA's vision</strong>
        <span>Evidence ↔ hypotheses ↔ decisions</span>
        <small>A branching, revisitable research record</small>
      </div>
    </div>
    <p><strong>The investigation is the enduring artifact.</strong> A research paper is one interpretation of it. SIGMA's long-term vision is to make the evidence, reasoning, questions, corrections, and decisions behind a result inspectable as a connected provenance graph.</p>
    <figure className="about-provenance-figure">
      <div className="about-provenance-diagram-scroll" role="region" tabIndex={0} aria-label="Investigation provenance diagram; scroll horizontally on narrow screens">
        <svg className="about-provenance-diagram" viewBox="0 0 910 625" role="img" aria-label="Vision for Investigation Provenance" aria-describedby="about-provenance-description" xmlns="http://www.w3.org/2000/svg">
          <desc id="about-provenance-description">Scientific papers contribute evidence, AI agents contribute analyses and hypotheses, and human investigators contribute observations and guidance to an evolving investigation graph. Evidence informs observations and hypotheses, contradictions trigger reassessment, and decisions guide further inquiry. Current Understanding and the Published TeX Document are two projections of that graph.</desc>
          <defs>
            {(['blue', 'green', 'gold', 'violet', 'coral'] as const).map(tone => <marker key={tone} id={`about-provenance-arrow-${tone}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M 0 0 L 8 4 L 0 8 z" fill={{ blue: '#78bbee', green: '#85cfa7', gold: 'var(--sigma-copper-foreground)', violet: '#b59ff5', coral: '#f0a098' }[tone]}/>
            </marker>)}
          </defs>

          <rect x="280" y="14" width="390" height="530" rx="18" fill="#0a1b2a" stroke="#5483a1" strokeWidth="1.5" strokeDasharray="6 5"/>
          <rect x="316" y="36" width="318" height="102" rx="14" fill="#153b55" stroke="#7dbde9" strokeWidth="2"/>
          <g fill="#bde5ff" stroke="#83c9f4" strokeWidth="1.6">
            <circle cx="351" cy="75" r="7"/><circle cx="381" cy="62" r="5"/><circle cx="389" cy="89" r="6"/>
            <path d="M 358 72 L 376 64 M 357 79 L 383 88 M 381 68 L 387 83"/>
          </g>
          <text x="411" y="76" fill="#f0f9ff" fontSize="19" fontWeight="700">Investigation</text>
          <text x="411" y="98" fill="#f0f9ff" fontSize="19" fontWeight="700">Provenance Graph</text>
          <text x="331" y="122" fill="#c2d9e9" fontSize="11.5">An evolving, source-attributed network of research</text>

          {/* Input arrows enter the graph and retain their different origins. */}
          <FlowArrow d="M 240 95 C 268 95 269 233 309 233" tone="blue"/>
          <FlowArrow d="M 240 225 L 264 225 L 264 176 L 563 176 L 563 197" tone="violet"/>
          <FlowArrow d="M 240 380 C 268 380 278 369 309 369" tone="green"/>

          {/* Relations within the investigation graph. */}
          <FlowArrow d="M 449 234 L 491 234" tone="gold"/>
          <FlowArrow d="M 380 267 L 380 329" tone="blue"/>
          <FlowArrow d="M 563 267 L 563 329" tone="violet"/>
          <FlowArrow d="M 449 366 L 491 366" tone="violet"/>
          <FlowArrow d="M 558 397 Q 548 432 508 448" tone="coral"/>
          <FlowArrow d="M 412 482 C 335 506 298 467 329 398" tone="green"/>

          {/* The research record produces multiple projections. */}
          <FlowArrow d="M 634 73 C 698 73 666 187 711 187" tone="blue"/>
          <FlowArrow d="M 634 105 C 691 105 666 379 711 379" tone="blue"/>

          <DiagramCard x={18} y={51} width={222} height={88} title="Scientific Papers" lines={['Cited research supplies claims,', 'data, findings, and references']} fill="#17324a" stroke="#65a5cf" titleColor="#bde5ff"/>
          <DiagramCard x={18} y={181} width={222} height={88} title="AI Agents" lines={['Interpret, question, challenge,', 'and synthesize evidence']} fill="#2b2148" stroke="#a793e8" titleColor="#ddceff"/>
          <DiagramCard x={18} y={336} width={222} height={88} title="Human Investigators" lines={['Observe, correct, judge, and', 'direct the research']} fill="#183b32" stroke="#74b99a" titleColor="#b5efce"/>

          <text x="381" y="188" textAnchor="middle" fill="var(--sigma-copper-foreground)" fontSize="11">supports / refutes</text>
          <text x="367" y="305" textAnchor="end" fill="#9bcfed" fontSize="11">informs</text>
          <text x="577" y="305" fill="#c5b5fd" fontSize="11">may conflict</text>
          <text x="471" y="354" textAnchor="middle" fill="#c5b5fd" fontSize="11">reveals</text>
          <text x="558" y="424" fill="#f0aaa3" fontSize="11">reassesses</text>
          <text x="353" y="515" fill="#a0dec0" fontSize="11">guides new inquiry</text>

          <DiagramCard x={310} y={199} width={139} height={68} title="Evidence" lines={['Claims, data,', 'citations']} fill="#403019" stroke="var(--sigma-copper-foreground)" titleColor="var(--sigma-copper-foreground)"/>
          <DiagramCard x={492} y={199} width={140} height={68} title="Hypotheses" lines={['Explanations,', 'models']} fill="#183b32" stroke="#85cfa7" titleColor="#b5efce"/>
          <DiagramCard x={310} y={330} width={139} height={68} title="Observations" lines={['Findings,', 'measurements']} fill="#17324a" stroke="#78bbee" titleColor="#bde5ff"/>
          <DiagramCard x={492} y={330} width={140} height={68} title="Contradictions" lines={['Conflicting claims,', 'open questions']} fill="#302345" stroke="#b59ff5" titleColor="#dfccff"/>
          <DiagramCard x={412} y={447} width={137} height={68} title="Decisions" lines={['Priorities, choices,', 'next steps']} fill="#432628" stroke="#f0a098" titleColor="#ffd0c9"/>

          <DiagramCard x={715} y={145} width={177} height={122} title="Current" lines={['Understanding', 'Living interpretation', 'of what is known', 'and still unresolved']} fill="#133741" stroke="#7ac4c7" titleColor="#b7f1ed"/>
          <DiagramCard x={715} y={333} width={177} height={122} title="Published TeX" lines={['Document', 'Citable narrative', 'derived from the', 'investigation']} fill="#2a2445" stroke="#aa9cda" titleColor="#ddd1ff"/>
          <text x="805" y="285" textAnchor="middle" fill="#9cb5c8" fontSize="11">projection</text>
          <text x="805" y="473" textAnchor="middle" fill="#9cb5c8" fontSize="11">projection</text>

          <text x="455" y="581" textAnchor="middle" fill="var(--sigma-copper-foreground)" fontSize="16" fontWeight="600">The investigation is the enduring artifact.</text>
          <text x="455" y="604" textAnchor="middle" fill="#b7cbd8" fontSize="14">The publication is one of its projections.</text>
        </svg>
      </div>
      <figcaption>Conceptual vision — the relationships shown are not yet a fully implemented provenance-graph feature.</figcaption>
    </figure>
    <p>Sources, AI responses, and human feedback would be distinguishable by origin but connected within the same research history. Papers are generally treated as evidence, not infallible truth; disputed claims and changing conclusions remain traceable.</p>
    <p>The aim is research that can be <strong>inspected, challenged, and extended</strong>, with a path backward from each published claim to its supporting evidence and reasoning.</p>
  </section>;
}

/** Architecture overview: shared visual vocabulary with the provenance vision. */
export function AboutResearchArchitecture() {
  const colors = { blue: '#78bbee', green: '#85cfa7', gold: 'var(--sigma-copper-foreground)', violet: '#b59ff5', coral: '#f0a098' };
  const Arrow = (props: Parameters<typeof FlowArrow>[0]) => <FlowArrow {...props} prefix="about-research-architecture"/>;
  return <section className="about-provenance" aria-label="Research Architecture">
    <p><strong>Research philosophy and evidence are distinct inputs.</strong> The Research Ethos guides how agents investigate; Source Material provides the supplied evidence they can reason from. SIGMA coordinates research, preserves findings, and synthesizes the record into a draft for human review.</p>
    <figure className="about-provenance-figure">
      <div className="about-provenance-diagram-scroll" role="region" tabIndex={0} aria-label="Research architecture diagram; scroll horizontally on narrow screens">
        <svg className="about-provenance-diagram" viewBox="0 0 910 620" role="img" aria-label="Research architecture and evidence flow" aria-describedby="about-research-architecture-description" xmlns="http://www.w3.org/2000/svg">
          <desc id="about-research-architecture-description">Research Ethos is frozen as behavioral instructions and Source Material is retrieved and compiled into bounded evidence. Both guide the research and paper generation. Investigator and Skeptic exchange findings, the Supervisor observes completed pairs and can nudge the next turn. Saved findings inform further research and paper generation. Dashed arrows show proposed Ethos-aware and historical supervision, not implemented capabilities.</desc>
          <defs>
            {(Object.keys(colors) as (keyof typeof colors)[]).map(tone => <marker key={tone} id={`about-research-architecture-arrow-${tone}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill={colors[tone]}/></marker>)}
          </defs>
          <rect x="280" y="38" width="390" height="330" rx="18" fill="#0a1b2a" stroke="#5483a1" strokeWidth="1.5"/>
          <text x="300" y="66" fontSize="19" fontWeight="700" fill="#f0f9ff">Research Session</text>
          <text x="300" y="85" fontSize="11.5" fill="#c2d9e9">Selected strategies · bounded agent turns</text>
          <Arrow d="M125 124 V145" tone="blue"/>
          <Arrow d="M125 324 V345" tone="green"/>
          <Arrow d="M232 181 H252 V110 H280" tone="blue"/>
          <Arrow d="M232 381 H266 V324 H280" tone="green"/>
          <Arrow d="M379 183 V239" tone="violet"/>
          <Arrow d="M300 279 H288 V145 H300" tone="violet"/>
          <Arrow d="M458 279 H572 V248" tone="gold"/>
          <Arrow d="M494 180 H477 V145 H458" tone="gold"/>
          <Arrow d="M232 160 H242 V17 H574 V155" tone="blue" dashed/>
          <Arrow d="M475 368 V414" tone="gold"/>
          <Arrow d="M655 438 H682 V203 H654" tone="gold" dashed/>
          <Arrow d="M295 454 H275 V350 H280" tone="gold"/>
          <Arrow d="M655 474 H699 V458 H715" tone="gold"/>
          <Arrow d="M655 452 H697 V304 H715" tone="blue"/>
          <Arrow d="M232 201 H247 V536 H760 V500" tone="blue"/>
          <Arrow d="M232 401 H260 V558 H825 V500" tone="green"/>
          <Arrow d="M803 500 V574" tone="violet"/>
          <DiagramCard x={18} y={50} width={214} height={74} title="Research Ethos" lines={['Research philosophy', 'Default or customized']} fill="#17324a" stroke="#65a5cf" titleColor="#bde5ff"/>
          <DiagramCard x={18} y={146} width={214} height={74} title="Frozen Ethos" lines={['Behavioral instructions', 'Versioned for the run']} fill="#17324a" stroke="#65a5cf" titleColor="#bde5ff"/>
          <DiagramCard x={18} y={250} width={214} height={74} title="Source Material" lines={['Supplied links and documents', 'With source provenance']} fill="#183b32" stroke="#74b99a" titleColor="#b5efce"/>
          <DiagramCard x={18} y={346} width={214} height={74} title="Evidence Compilation" lines={['Retrieve · Extract · Freeze', 'Bounded source excerpts']} fill="#183b32" stroke="#74b99a" titleColor="#b5efce"/>
          <DiagramCard x={300} y={105} width={158} height={78} title="Investigator" lines={['Develops ideas,', 'arguments and tests']} fill="#2b2148" stroke="#a793e8" titleColor="#ddceff"/>
          <DiagramCard x={300} y={240} width={158} height={78} title="Skeptic" lines={['Challenges claims,', 'tests assumptions']} fill="#2b2148" stroke="#a793e8" titleColor="#ddceff"/>
          <DiagramCard x={494} y={156} width={160} height={92} title="Supervisor" lines={['Process review', 'Optional nudges', 'Not a research agent']} fill="#403019" stroke="var(--sigma-copper-foreground)" titleColor="var(--sigma-copper-foreground)"/>
          <text x="391" y="210" fontSize="11" fill="#c5b5fd">review</text>
          <text x="481" y="270" fontSize="11" fill="var(--sigma-copper-foreground)">observes</text>
          <text x="485" y="132" fontSize="11" fill="var(--sigma-copper-foreground)">next-turn nudge</text>
          <text x="391" y="340" fontSize="11" fill="#b7cbd8" textAnchor="middle">Repeat within configured limits</text>
          <text x="584" y="30" fontSize="11" fill="#9bcfed">Ethos alignment*</text>
          <DiagramCard x={295} y={414} width={360} height={86} title="Cumulative Research Findings" lines={['Arguments, evidence, objections and test results', 'Open questions and preserved research history']} fill="#153b55" stroke="#7dbde9" titleColor="#bde5ff"/>
          <text x="486" y="399" fontSize="11" fill="var(--sigma-copper-foreground)">save</text>
          <text x="290" y="390" fontSize="11" fill="var(--sigma-copper-foreground)">reuse</text>
          <text x="686" y="395" fontSize="11" fill="var(--sigma-copper-foreground)" transform="rotate(-90 686 395)">historical context*</text>
          <DiagramCard x={715} y={265} width={177} height={78} title="Current Understanding" lines={['Synthesis of findings', 'and unresolved questions']} fill="#133741" stroke="#7ac4c7" titleColor="#b7f1ed"/>
          <DiagramCard x={715} y={414} width={177} height={86} title="Paper Generation" lines={['Review · Extract · Write', 'Validate · Proofread']} fill="#2a2445" stroke="#aa9cda" titleColor="#ddd1ff"/>
          <text x="460" y="529" fontSize="11" fill="#9bcfed" textAnchor="middle">research philosophy</text>
          <text x="460" y="551" fontSize="11" fill="#a0dec0" textAnchor="middle">source evidence</text>
          <DiagramCard x={715} y={574} width={177} height={38} title="PDF / TeX Draft" lines={[]} fill="#2a2445" stroke="#aa9cda" titleColor="#ddd1ff"/>
          <text x="18" y="597" fontSize="11.5" fill="#b7cbd8">* Dashed paths: proposed Supervisor enhancements.</text>
        </svg>
      </div>
      <figcaption>Solid arrows describe the implemented research flow. Dashed arrows show planned Ethos-aware supervision and longitudinal context. The paper stage uses its own frozen Ethos snapshot and bounded source evidence; drafts require human review.</figcaption>
    </figure>
  </section>;
}
