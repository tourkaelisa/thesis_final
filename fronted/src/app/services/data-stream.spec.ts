import { TestBed } from '@angular/core/testing';

import { DataStream } from './data-stream';

describe('DataStream', () => {
  let service: DataStream;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(DataStream);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
