// Teacher-studio fixtures (NEXT_PUBLIC_USE_MOCKS=true). Read-only: generation needs the real backend.
import type { StudentSubjects, SubjectDetail, SubjectList, SubjectSummary } from "../types";

const tid = () => `tr_mock_${Math.random().toString(36).slice(2, 8)}`;

const DEFAULT: SubjectSummary = {
  id: "data_structures", name: "Data Structures", description: "Arrays to graphs: the built-in Rootwise course.",
  status: "published", is_default: true, n_concepts: 21, n_questions: 73, n_flashcards: 0, n_documents: 0,
  n_students: 1, created_at: "2026-01-01T00:00:00", published_at: "2026-01-01T00:00:00", job: null,
};

const unavailable = async (): Promise<never> => {
  throw new Error("The teacher studio needs the real backend (mock mode is read-only).");
};

export const mockStudio = {
  async studentSubjects(student_id: string): Promise<StudentSubjects> {
    return { trace_id: tid(), student_id, subjects: [{ id: DEFAULT.id, name: DEFAULT.name, description: DEFAULT.description,
      is_default: true, n_concepts: DEFAULT.n_concepts }] };
  },
  async subjects(): Promise<SubjectList> {
    return { trace_id: tid(), subjects: [DEFAULT] };
  },
  async subject(): Promise<SubjectDetail> {
    return { trace_id: tid(), subject: DEFAULT, documents: [], worlds: [], diagnostic_concepts: [], warnings: [],
      publish_blockers: [], editable: false };
  },
  createSubject: unavailable,
  addDocuments: unavailable,
  regenerate: unavailable,
  publish: unavailable,
  unpublish: unavailable,
  deleteSubject: unavailable,
  studioGraph: unavailable,
  studioConcept: unavailable,
  patchConcept: unavailable,
  deleteConcept: unavailable,
  patchQuestion: unavailable,
  deleteQuestion: unavailable,
  createFlashcard: unavailable,
  patchFlashcard: unavailable,
  deleteFlashcard: unavailable,
  enrollment: unavailable,
  setEnrollment: unavailable,
};
