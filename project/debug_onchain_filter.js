import { Connection, PublicKey } from '@solana/web3.js';

async function testOnChainFilterCalls() {
  console.log('🔍 Testing OnChain filter RPC calls exactly as bot does...\n');
  
  const rpcEndpoints = [
    'https://solana.drpc.org',
    'https://api.mainnet-beta.solana.com',
    'https://solana-mainnet.g.alchemy.com/v2/demo',
    'https://rpc.helius.xyz/?api-key=demo'
  ];
  
  const testToken = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'; // USDC
  
  for (const endpoint of rpcEndpoints) {
    console.log(`\n📡 Testing endpoint: ${endpoint.replace(/api-key=[\w-]+/gi, 'api-key=***')}`);
    
    try {
      const connection = new Connection(endpoint, {
        commitment: 'processed',
        confirmTransactionInitialTimeout: 5000,
        disableRetryOnRateLimit: false,
        httpHeaders: {
          'Content-Type': 'application/json'
        }
      });
      
      const mintPubkey = new PublicKey(testToken);
      
      console.log('  Testing getAccountInfo...');
      const accountStart = Date.now();
      try {
        const accountInfo = await connection.getAccountInfo(mintPubkey);
        console.log(`  ✅ getAccountInfo: ${accountInfo ? 'Success' : 'No data'}, ${Date.now() - accountStart}ms`);
      } catch (error) {
        console.log(`  ❌ getAccountInfo failed: ${error.message}`);
      }
      
      console.log('  Testing getTokenSupply...');
      const supplyStart = Date.now();
      try {
        const supply = await connection.getTokenSupply(mintPubkey);
        console.log(`  ✅ getTokenSupply: ${supply?.value?.amount || 'No supply'}, ${Date.now() - supplyStart}ms`);
      } catch (error) {
        console.log(`  ❌ getTokenSupply failed: ${error.message}`);
      }
      
      console.log('  Testing getTokenLargestAccounts...');
      const accountsStart = Date.now();
      try {
        const accounts = await connection.getTokenLargestAccounts(mintPubkey);
        console.log(`  ✅ getTokenLargestAccounts: ${accounts?.value?.length || 0} accounts, ${Date.now() - accountsStart}ms`);
      } catch (error) {
        console.log(`  ❌ getTokenLargestAccounts failed: ${error.message}`);
      }
      
    } catch (error) {
      console.log(`  ❌ Connection failed: ${error.message}`);
    }
  }
}

testOnChainFilterCalls().catch(console.error);
