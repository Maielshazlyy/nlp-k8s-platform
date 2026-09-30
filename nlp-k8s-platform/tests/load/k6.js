import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 },
    { duration: '2m',  target: 80 },   // push CPU past the HPA threshold
    { duration: '30s', target: 0 },
  ],
  thresholds: { http_req_failed: ['rate<0.01'], http_req_duration: ['p(95)<1500'] },
};

const phrases = ['great product', 'terrible support', 'it was fine', 'I hate waiting', 'best day ever'];

export default function () {
  // unique suffix defeats the cache so we actually stress inference
  const texts = phrases.map((p) => `${p} ${Math.random()}`);
  const res = http.post('http://nlp.localtest.me/v1/sentiment', JSON.stringify({ texts }),
    { headers: { 'Content-Type': 'application/json' } });
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(0.2);
}
