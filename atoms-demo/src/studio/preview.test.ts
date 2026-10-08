import { describe, expect, it } from 'vitest';
import { buildPreviewDocument } from './preview';


describe('sandbox preview document', () => {
  it('injects CSP and storage bridge without damaging generated scripts', () => {
    const html = '<!doctype html><html><head><title>Demo</title></head><body><script>document.body.dataset.ready="yes";</script></body></html>';
    const result = buildPreviewDocument(html, 'project-1');

    expect(result).toContain('Content-Security-Policy');
    expect(result).toContain("connect-src 'none'");
    expect(result).toContain('window.demoStorage');
    expect(result).toContain('<script>document.body.dataset.ready="yes";</script>');
  });

  it('creates a head when generated HTML omitted one', () => {
    const html = '<html><body><script>document.body.textContent="ok";</script></body></html>';
    expect(buildPreviewDocument(html, 'project-2')).toContain('<head><meta http-equiv="Content-Security-Policy"');
  });
});
