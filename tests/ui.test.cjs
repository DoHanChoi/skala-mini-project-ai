/** 기존 Vue 스크립트를 VM에서 실행해 공개 응답 표시와 사용자 동작을 검증한다. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'web_chat.html'), 'utf8');
const script = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m => m[1]).find(s => s.includes('createApp'));

/** Vue 반응성과 SSE·DOM의 경계만 대체하고 실제 화면 스크립트를 실행한다. */
function harness() {
  let setup;
  const streams = [];
  const nodes = new Map();
  const context = vm.createContext({
    Vue: {createApp: options => { setup = options.setup; return {mount() {}}; },
      ref: value => ({value}), reactive: value => value, nextTick: async () => {}},
    fetch: async () => ({json: async () => ({llm_backend: 'fake', fast_llm: 'fast', quality_llm: 'quality'})}),
    document: {getElementById: id => nodes.get(id)},
    EventSource: class {
      constructor(url) { this.url = url; this.closed = false; streams.push(this); }
      close() { this.closed = true; }
      emit(data) { this.onmessage({data: typeof data === 'string' ? data : JSON.stringify(data)}); }
    },
  });
  vm.runInContext(script, context);
  return {api: setup(), context, streams, nodes};
}

/** 서로 다른 요청에서도 같은 시스템 이름을 사용하는 근거를 구성한다. */
function passedAnswer(request = 'request-a') {
  const id = `ev:${request}:0`;
  return {type: 'FinalAnswer', reply: '서버의 확정 답변',
    diagnosis: {observations: [{system_name: 'payments-service', metric: 'cpu_percent', value: 91, unit: '%', evidence_id: id}],
      hypotheses: [{text: '부하 증가 가능성', evidence_ids: [id]}],
      actions: [{text: '매뉴얼을 검토하세요', evidence_ids: [`ev:${request}:1`]}]},
    evidence: [{id, source: 'monitoring', available: true, system_name: 'payments-service', target: 'payments-service',
      raw: {cpu_percent: 91}, eligible_metrics: ['cpu_percent'], issues: []},
      {id: `ev:${request}:1`, source: 'runbook', available: true, title: 'CPU 대응', raw: '# 매뉴얼', issues: []}],
    validation: {status: 'passed', passed: true, attempt: 2, scope: 'observed_values_and_source_links', errors: []}};
}

/** 실제 submit 핸들러를 거쳐 생성된 SSE 대역을 반환한다. */
function submit(h, message = 'payments-service 장애') {
  h.api.input.value = message;
  h.api.onSubmit();
  return h.streams.at(-1);
}

/** VM 객체와 일반 객체의 프로토타입 차이를 제외하고 JSON 내용을 비교한다. */
function json(value) {
  return JSON.parse(JSON.stringify(value));
}

test('성공 상태와 세 진단 구역·시도 횟수를 유지하고 원본을 변경하지 않는다', () => {
  const h = harness();
  const answer = passedAnswer();
  const original = JSON.stringify(answer);
  const view = h.context.answerView(answer);
  assert.equal(view.status, 'passed');
  assert.equal(view.attempt, 2);
  assert.deepEqual(json(view.diagnosis), answer.diagnosis);
  assert.match(view.notice, /가설·조치의 의미는 검증하지/);
  assert.equal(JSON.stringify(answer), original);
});

test('검증 실패는 잘못 전달된 diagnosis가 있어도 표시하지 않고 오류만 제공한다', () => {
  const h = harness();
  const answer = passedAnswer();
  answer.validation = {status: 'failed', passed: false, attempt: 3,
    errors: [{code: 'invalid_structure', path: 'draft', message: '구조 오류'}]};
  const view = h.context.answerView(answer);
  assert.equal(view.status, 'failed');
  assert.equal(view.diagnosis, null);
  assert.equal(view.attempt, 3);
  assert.equal(view.errors.length, 1);
  assert.match(view.notice, /실패한 초안/);
});

test('일반 대화와 v1은 비대상이며 성공으로 표시하지 않는다', () => {
  const h = harness();
  for (const reason of ['general_chat', 'legacy_v1']) {
    const view = h.context.answerView({validation: {status: 'not_applicable', passed: null, reason}, diagnosis: passedAnswer().diagnosis});
    assert.equal(view.status, 'not-applicable');
    assert.equal(view.diagnosis, null);
    assert.match(view.label, reason === 'general_chat' ? /일반 대화/ : /v1/);
    assert.equal(view.attempt, null);
  }
});

test('메타데이터 누락·모순·미지원 범위·불완전한 진단은 상태 확인 불가다', () => {
  const h = harness();
  const good = passedAnswer();
  for (const answer of [{reply: 'old'}, {...good, validation: {...good.validation, passed: false}},
    {...good, validation: {...good.validation, scope: 'unknown'}}, {...good, diagnosis: {}},
    {...good, diagnosis: {...good.diagnosis, observations: [null]}},
    {...good, diagnosis: {...good.diagnosis, actions: [{text: 'bad', evidence_ids: null}]}}]) {
    const view = h.context.answerView(answer);
    assert.equal(view.status, 'unknown');
    assert.equal(view.diagnosis, null);
  }
});

test('같은 근거 ID라도 답변별 DOM 위치가 다르고 다른 요청을 참조하지 않는다', () => {
  const h = harness();
  const a = {id: 2, view: h.context.answerView(passedAnswer('same'))};
  const b = {id: 5, view: h.context.answerView(passedAnswer('same'))};
  assert.equal(h.context.sourceDomId(a, 'ev:same:0'), 'evidence-2-0');
  assert.equal(h.context.sourceDomId(b, 'ev:same:0'), 'evidence-5-0');
  assert.equal(h.context.sourceDomId(a, 'ev:other:0'), null);
  assert.equal(h.context.sourceLabel(a, 'ev:other:0'), '출처 없음');
});

test('근거 버튼은 해당 details만 열고 summary에 초점을 준다', async () => {
  const h = harness();
  const item = {id: 8, view: h.context.answerView(passedAnswer())};
  let focused = false;
  let scrolled = false;
  const details = {open: false, querySelector: selector => { assert.equal(selector, 'summary');
    return {focus: () => { focused = true; }}; }, scrollIntoView: () => { scrolled = true; }};
  h.nodes.set('evidence-8-1', details);
  await h.api.showEvidence(item, 'ev:request-a:1');
  assert.equal(details.open, true);
  assert.equal(focused, true);
  assert.equal(scrolled, true);
  await h.api.showEvidence(item, 'missing');
});

test('원본 HTML·Markdown·비유한 수치 태그와 활용 제한을 텍스트로 보존한다', () => {
  const h = harness();
  const raw = '<img src=x onerror="alert(1)">\n[클릭](javascript:alert(1))';
  assert.equal(h.context.rawText(raw), raw);
  assert.match(h.context.rawText({cpu_percent: {nonfinite_number: 'nan'}}), /nonfinite_number/);
  assert.equal(h.context.issueLabel('unknown_system'), '미인식 시스템');
  assert.equal(h.context.issueLabel('runbook_not_found'), '매뉴얼 없음');
  assert.equal(h.context.metricLabel('cpu_percent'), 'CPU 사용률');
  assert.doesNotMatch(html, /v-html|innerHTML|v-bind:href|:href/);
});

test('최종 응답 하나로 구역을 연결하고 다음 답변의 근거와 섞이지 않는다', () => {
  const h = harness();
  const first = submit(h);
  first.emit({type: 'DraftWritten', attempt: 1});
  assert.equal(h.api.log.value.filter(i => i.kind === 'agent').length, 0);
  first.emit(passedAnswer('first'));
  first.emit('[DONE]');
  assert.equal(first.closed, true);
  assert.equal(h.api.sending.value, false);
  const second = submit(h);
  second.emit(passedAnswer('second'));
  second.emit('[DONE]');
  const answers = h.api.log.value.filter(i => i.kind === 'agent');
  assert.equal(answers.length, 2);
  assert.equal(answers[0].view.evidence[0].id, 'ev:first:0');
  assert.equal(answers[1].view.evidence[0].id, 'ev:second:0');
  assert.ok(h.api.log.value.filter(i => i.kind === 'steps').every(i => i.complete));
});

test('일반 대화 토큰과 최종 답변은 같은 말풍선을 사용하고 중복 제출을 막는다', () => {
  const h = harness();
  const stream = submit(h, '안녕하세요');
  submit(h, '중복 요청');
  assert.equal(h.streams.length, 1);
  stream.emit({type: 'AnswerToken', delta: '안녕'});
  stream.emit({type: 'AnswerToken', delta: '하세요'});
  assert.equal(h.api.log.value.at(-1).text, '안녕하세요');
  stream.emit({type: 'FinalAnswer', reply: '안녕하세요!', validation: {status: 'not_applicable', passed: null, reason: 'general_chat'}});
  stream.emit('[DONE]');
  const answers = h.api.log.value.filter(i => i.kind === 'agent');
  assert.equal(answers.length, 1);
  assert.equal(answers[0].text, '안녕하세요!');
  assert.equal(answers[0].view.status, 'not-applicable');
});

test('연결 오류 후 입력을 다시 허용하고 성공 표시를 만들지 않는다', () => {
  const h = harness();
  const stream = submit(h);
  stream.onerror();
  assert.equal(h.api.sending.value, false);
  assert.equal(stream.closed, true);
  assert.equal(h.api.log.value.filter(i => i.kind === 'agent').length, 0);
});

test('대상이 없는 v1 진행 이벤트에 undefined 시스템명을 표시하지 않는다', () => {
  const h = harness();
  const stream = submit(h, 'v1 장애');
  stream.emit({type: 'TaskCompleted', source: 'monitoring', retries: 0});
  const steps = h.api.log.value.find(i => i.kind === 'steps').steps;
  assert.deepEqual(json(steps), ['모니터링 지표 확인']);
});

test('객체가 아닌 SSE JSON과 깨진 프레임은 무시하고 다음 정상 응답을 처리한다', () => {
  const h = harness();
  const stream = submit(h);
  for (const invalid of ['null', '[]', '1', '"text"', '{broken']) stream.emit(invalid);
  stream.emit(passedAnswer());
  stream.emit('[DONE]');
  assert.equal(h.api.log.value.filter(i => i.kind === 'agent').length, 1);
  assert.equal(h.api.sending.value, false);
});
