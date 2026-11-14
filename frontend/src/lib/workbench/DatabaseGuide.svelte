<script lang="ts">
  import { t } from '../i18n.svelte';
  import { preciseMoney } from '../format';
  import type { Catalog } from '../types';
  let { catalog }: { catalog: Catalog } = $props();

  const metrics = [
    {
      title: 'Reads per second',
      model: 'Reads counts weighted query work arriving at a database. One chat history request uses 1.8 read units. The Reads meter divides this demand by the lower of the read processing limit, the disk read limit and any legacy read throttle.',
      advice: 'At capacity, requests slow down and some fail. Add CPU or RAM for read processing, or NVMe when disk is limiting. Cache repeated reads or split eligible reads with a replica. More storage space leaves read speed unchanged. Hardware and extra components add cost. Cache entries and replica data can be stale.'
    },
    {
      title: 'Writes per second',
      model: 'Writes counts weighted application write work reaching a primary. Sending a message uses 1 write unit, an image upload uses 1.5, and authentication uses 0.25 plus 1 read unit. The Writes meter compares demand with the standalone write limit for CPU, disk and any legacy throttle. The message search index raises compute and disk work per write by 20%.',
      advice: 'At capacity, writes and other requests sharing that database can fail. Add CPU for compute pressure, NVMe for disk pressure, or remove a binding legacy throttle in configuration. Extra replicas and caches leave application write demand unchanged. They can free shared resources when reads contribute to the bottleneck. Replication itself adds disk work.'
    },
    {
      title: 'Disk I/O utilization',
      model: 'Disk I/O adds read units divided by the disk read budget and write units divided by the disk write budget. SSD budgets are 420 read units/s or 115 write units/s if used alone. NVMe raises both by 45%. Each available follower adds 8% of base disk work per primary write. Replicas use their own disk to replay committed writes.',
      advice: 'A combined load above 100% throttles throughput even when Reads and Writes each show less than 100%. NVMe helps when disk is limiting and adds 35% of base daily cost. Extra GB of storage space leave the I/O budget unchanged. A cache or replica can help when eligible reads contribute enough load.'
    },
    {
      title: 'CPU utilization',
      model: 'CPU shows the larger of read and write compute pressure. At 2 vCPUs and 8 GB RAM, the compute limits are 155 read units/s and 62 write units/s before indexing. Both grow with (vCPU / 2) to the power of 0.74. Read compute also scales with (RAM / 8) to the power of 0.22.',
      advice: 'At capacity, the database admits fewer requests. More vCPUs raise compute capacity with diminishing returns and higher daily cost. NVMe leaves compute capacity unchanged. RAM improves read processing and memory headroom while the write compute limit is set by CPU.'
    },
    {
      title: 'Memory utilization',
      model: 'The memory estimate is 0.8 GB base plus 0.014 GB per incoming read unit/s and 0.02 GB per write or replay unit/s, divided by configured RAM.',
      advice: 'High memory pressure slows traffic and saturation reduces throughput. Add RAM or reduce eligible read load. More disk speed or connection slots leave the memory budget unchanged. RAM upgrades raise daily cost.'
    },
    {
      title: 'Connection limits',
      model: 'The database pool is an admission budget. The Connections meter divides incoming read and write or replay units per second by the configured limit. It does not count sockets or the Messenger’s persistent client connections.',
      advice: 'When the pool binds, raising it admits more work if compute, memory and disk have room. Raising it has no effect on those limits. The pool setting has no additional operating charge in this simulation.'
    },
    {
      title: 'Storage types and space',
      model: 'SSD and NVMe set the I/O budget. Storage (GB) sets the volume available for persistent data. Messenger images, voice messages and files consume more space than texts. Media quality affects bytes stored.',
      advice: 'When a data volume fills up, writes are limited and reads can continue. Add GB or reduce media quality to conserve space. NVMe alone leaves free space unchanged. Extra space and NVMe raise costs, and lower media quality can reduce user satisfaction.'
    },
    {
      title: 'Database throughput',
      model: 'Throughput counts completed application requests per second. Demand meters use work arriving after upstream routing and throttling. The largest capacity ratio determines the share of requests served, with a separate check for available storage on writes. Incidents can reduce effective capacity.',
      advice: 'Near capacity, latency grows. Above it, requests are dropped. Sustainable writes estimates how many write units can fit while current reads keep their share and the write mix stays the same. It can be lower than the standalone Writes limit. Preview upgrades using the draft forecast and check the operating cost.'
    },
    {
      title: 'Replication lag',
      model: 'Each replica receives the write units its primary commits. The replica replays them using its own CPU, RAM, disk and pool while serving reads. Unapplied work carries into the next step. Lag estimates how long the remaining work takes to replay at the current rate, plus 0.2 seconds. If there is pending work and no replay, lag cannot be estimated.',
      advice: 'A replica can still serve reads while catching up, so reads may trail the primary. Upgrade the pressured replica resource or reduce its read load to help it catch up. Increasing primary storage space does not make replay faster. The simulation tracks write work and lag without storing individual messages or comparing versions.'
    }
  ];
</script>

<section id="database-guide" class="panel pad stack">
  <h2>{t('Database Guide')}</h2>
  <h3>{t('Primary and read replicas')}</h3>
  <p>{t('The primary is authoritative for its dataset. It handles all application writes, any reads bundled with writes, and indexed search when required. It can also serve ordinary reads. A read replica follows one primary and serves eligible application reads without accepting application writes.')}</p>
  <p>{t('An API uses one directly connected primary for its dataset. In older layouts with several primary links, the first by component ID is selected. Independent primaries hold independent datasets. An upstream balancer can distribute traffic across APIs, but it has no dataset-aware routing and does not replicate or shard the data.')}</p>
  <p>{t('The API splits eligible reads evenly between its linked primary and linked replicas that follow that primary. Failed replicas are skipped. If caches are attached, they receive ordinary reads first. Cache misses use the cache’s eligible data links, or the originating API’s links when the cache has none eligible. A saturated target keeps its share of the load.')}</p>
  <h4>{t('Connect a replica in Messenger')}</h4>
  <ol>
    <li>{t('In Topology, keep Messenger API → Primary database for writes and reads.')}</li>
    <li>{t('Add a Read replica in Draft. Connect Read replica → Primary database to subscribe it to changes.')}</li>
    <li>{t('Connect Messenger API → Read replica for direct reads, or Cache → Read replica to send cache misses there.')}</li>
    <li>{t('Link the primary and replica to deployed Monitoring with free slots. Review and deploy the draft, then check read demand and replication lag.')}</li>
  </ol>
  <h3>{t('Cache versus read replica')}</h3>
  <div class="comparison">
    <div class="stack">
      <h4>{t('Cache')}</h4>
      <p>{t('A hit serves a repeated read from memory with a 4 ms base component latency. A miss still visits a database. Use History only for repeated chat history reads or All reads for ordinary cacheable Messenger reads such as conversation lists.')}</p>
      <p>{t('The hit estimate improves with memory relative to the audience, longer TTL and LFU. TTL represents how long a cached value can be reused. There is no per-message invalidation or write-through. The simulator estimates hit rate without tracking cached values or stale responses.')}</p>
      <p>{preciseMoney(catalog.components.cache.daily)} {t('base daily cost')}</p>
    </div>
    <div class="stack">
      <h4>{t('Read replica')}</h4>
      <p>{t('A replica processes queries with a 21 ms base component latency. Use it to distribute ordinary reads, including misses and reads that are rarely repeated. It replays committed writes continuously in simulation steps instead of relying on a TTL.')}</p>
      <p>{t('Replication has its own hardware cost and uses I/O on both servers. Read freshness depends on replay lag. Use the primary for Messenger writes and the reads that must stay with them.')}</p>
      <p>{preciseMoney(catalog.components.replica.daily)} {t('base daily cost')}</p>
    </div>
  </div>
  <ul>
    <li>{t('API → Primary is the starting point for writes and reads.')}</li>
    <li>{t('API → Cache → Primary is useful for repeated history reads. Keep API → Primary for writes.')}</li>
    <li>{t('API → Primary and API → Replica share eligible reads. Replica → Primary subscribes to committed writes.')}</li>
    <li>{t('API → Cache → Replica can offload both repeated reads and misses. Keep API → Primary and Replica → Primary.')}</li>
  </ul>
  <h3>{t('Database metrics')}</h3>
  {#each metrics as metric (metric.title)}
    <details>
      <summary>{t(metric.title)}</summary>
      <p>{t(metric.model)}</p>
      <p>{t(metric.advice)}</p>
    </details>
  {/each}
</section>

<style>
  section { scroll-margin-top: 24px; }
  h3 { margin-top: 5px; }
  ul, ol { margin: 0; padding-inline-start: 24px; }
  li + li { margin-top: 5px; }
  .comparison { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .comparison > div, details { background: var(--rail); border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
  summary { cursor: pointer; font-weight: 600; }
  details p { margin: 8px 0 0; }
  @media (max-width: 650px) { .comparison { grid-template-columns: 1fr; } }
</style>
