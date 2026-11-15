import { nav, target } from './onboarding';

export const engineeringLessons = [
  { title: 'Research Service Decomposition', text: 'Start Service Decomposition in Product and run the clock until it completes. Research pays for development; infrastructure is still configured and deployed separately.', target: 'engineering.research' as const, open: 'product' as const },
  { title: 'Create a specialized service', text: 'Create a draft and add an API. Open its configuration and select Accounts. Keep the existing Universal API connected so current features remain served. You may skip a step and resume this lesson later.', target: target.add, open: 'build' as const },
  { title: 'Connect service dependencies', text: 'Connect the balancer to Accounts and Accounts to the same primary as Universal. A Messaging, Media or Search service also needs a directed link to Accounts. If your topology differs, keep Universal as a safe fallback and inspect the Guide.', target: target.connect, open: 'build' as const },
  { title: 'Review the same workload', text: 'Open Review. Check operation coverage, database ownership, projected availability and both installation and daily costs. Resolve errors before deployment; keep the draft if the change is not affordable.', target: target.review, open: 'build' as const },
  { title: 'Deploy the service architecture', text: 'Deploy the reviewed draft. Research never deploys services automatically. Moving a domain or changing partitions starts paid preparation while the old topology continues serving.', target: target.deploy, open: 'build' as const },
  { title: 'Observe specialized traffic', text: 'Open Telemetry, then inspect covered API and database nodes. Compare requests by operation, utilization, domain demand and cost. Add monitoring links in a draft if metrics are missing. Universal remains a valid architecture.', target: target.coverage, open: 'monitor' as const }
];
