import { describe, expect, it } from "vitest";
import { createPatientProfileHttp } from "./patientProfileHttp";
import { makeErrorEnvelope, makeHistory, makeRevision } from "./patientProfileFixtures";
import {
  PatientProfileApiError,
  PatientProfileDecodeError,
} from "./patientProfileViewModels";

function jsonResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function failingFetch(
  status: number,
  body: unknown,
): typeof fetch {
  return (() => Promise.resolve(jsonResponse(body, status))) as typeof fetch;
}

function capturingFetch(
  onCall: (input: RequestInfo | URL, init?: RequestInit) => Response | Promise<Response>,
): typeof fetch {
  return ((input, init) =>
    Promise.resolve(onCall(input, init))) as typeof fetch;
}

describe("createPatientProfileHttp", () => {
  it("reads the latest profile via the Slice 5.5 endpoint", async () => {
    let requestedUrl = "";
    const repo = createPatientProfileHttp({
      fetchImpl: capturingFetch((input) => {
        requestedUrl = String(input);
        return jsonResponse(makeRevision());
      }),
    });
    const view = await repo.getLatestPatientProfile("subject-1", "episode-1");
    expect(requestedUrl).toBe(
      "/api/v2/subjects/subject-1/review-episodes/episode-1/patient-profile",
    );
    expect(view.revisionId).toBe("profile-revision-1");
    expect(view.lanes).toHaveLength(13);
  });

  it("URL-encodes subject and episode identifiers", async () => {
    const urls: string[] = [];
    const repo = createPatientProfileHttp({
      fetchImpl: capturingFetch((input) => {
        urls.push(String(input));
        return jsonResponse(makeRevision());
      }),
    });
    await repo.getLatestPatientProfile("sub ject/1", "ep/1");
    expect(urls[0]).toBe(
      "/api/v2/subjects/sub%20ject%2F1/review-episodes/ep%2F1/patient-profile",
    );
  });

  it("lists history via the history endpoint", async () => {
    let requestedUrl = "";
    const repo = createPatientProfileHttp({
      fetchImpl: capturingFetch((input) => {
        requestedUrl = String(input);
        return jsonResponse(makeHistory());
      }),
    });
    const view = await repo.listPatientProfileHistory("subject-1", "episode-1");
    expect(requestedUrl).toBe(
      "/api/v2/subjects/subject-1/review-episodes/episode-1/patient-profile/history",
    );
    expect(view.items).toHaveLength(2);
  });

  it("reads a frozen revision by id via the revisions endpoint", async () => {
    let requestedUrl = "";
    const repo = createPatientProfileHttp({
      fetchImpl: capturingFetch((input) => {
        requestedUrl = String(input);
        return jsonResponse(makeRevision());
      }),
    });
    const view = await repo.getPatientProfileRevision(
      "subject-1",
      "profile-revision-1",
    );
    expect(requestedUrl).toBe(
      "/api/v2/subjects/subject-1/patient-profile-revisions/profile-revision-1",
    );
    expect(view.revisionId).toBe("profile-revision-1");
  });

  it("forwards the abort signal", async () => {
    const repo = createPatientProfileHttp({
      fetchImpl: capturingFetch((_input, init) => {
        expect(init?.signal).toBeInstanceOf(AbortSignal);
        return jsonResponse(makeRevision());
      }),
    });
    const controller = new AbortController();
    await repo.getLatestPatientProfile("subject-1", "episode-1", {
      signal: controller.signal,
    });
  });

  it("decodes the error envelope into a PatientProfileApiError on 4xx", async () => {
    const repo = createPatientProfileHttp({
      fetchImpl: failingFetch(404, makeErrorEnvelope()),
    });
    const error = await repo
      .getLatestPatientProfile("subject-1", "episode-1")
      .then(
        () => null,
        (caught: unknown) => caught,
      );
    expect(error).toBeInstanceOf(PatientProfileApiError);
    if (error instanceof PatientProfileApiError) {
      expect(error.code).toBe("NOT_FOUND");
      expect(error.statusCode).toBe(404);
      expect(error.title).toBe("未找到");
    }
  });

  it("maps a non-envelope failure to INVALID_RESPONSE", async () => {
    const repo = createPatientProfileHttp({
      fetchImpl: failingFetch(500, "<html>gateway error</html>"),
    });
    const error = await repo
      .getLatestPatientProfile("subject-1", "episode-1")
      .then(
        () => null,
        (caught: unknown) => caught,
      );
    expect(error).toBeInstanceOf(PatientProfileApiError);
    if (error instanceof PatientProfileApiError) {
      expect(error.code).toBe("INVALID_RESPONSE");
      expect(error.statusCode).toBe(500);
    }
  });

  it("rejects an unparseable 2xx body as INVALID_RESPONSE", async () => {
    const repo = createPatientProfileHttp({
      fetchImpl: (() =>
        Promise.resolve(new Response("<html>oops</html>", { status: 200 }))) as typeof fetch,
    });
    await expect(
      repo.getLatestPatientProfile("subject-1", "episode-1"),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });

  it("propagates strict decode failures instead of guessing", async () => {
    const wire = { ...makeRevision(), schema_version: "phase5/v2" };
    const repo = createPatientProfileHttp({
      fetchImpl: () => Promise.resolve(jsonResponse(wire)),
    });
    await expect(
      repo.getLatestPatientProfile("subject-1", "episode-1"),
    ).rejects.toBeInstanceOf(PatientProfileDecodeError);
  });
});
