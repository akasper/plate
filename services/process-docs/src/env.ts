export interface Env {
  /** PLATE git release tag baked in at deploy time (see `npm run bundle`). */
  RELEASE_TAG: string;
  /** When set to `fixture`, uses embedded test fixtures (unit tests). */
  DOC_SOURCE?: string;
}