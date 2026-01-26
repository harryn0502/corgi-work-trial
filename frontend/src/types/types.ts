export interface Iteration {
  iteration: number;
  estimate: number;
  reasoning: string;
}

export interface Results {
  tracking_number: string;
  ground_truth: number;
  iterations: Iteration[];
}
